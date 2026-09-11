import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.models import CodeChunk, CodeFile, Repository
from app.services.code_parser import IGNORE_DIRS, code_parser
from app.services.vector_store import vector_store


class GitHubService:
    """Service to clone, ingest, parse, and index repositories into vector storage."""

    async def ingest_directory(
        self,
        db: AsyncSession,
        repo: Repository,
        directory_path: Path,
        progress_callback=None
    ) -> Dict[str, int]:
        """Traverse directory, parse source files, generate embeddings, and persist chunks."""
        # 1. Clear any prior files/chunks for clean re-indexing
        await db.execute(delete(CodeChunk).where(CodeChunk.repo_id == repo.id))
        await db.execute(delete(CodeFile).where(CodeFile.repo_id == repo.id))
        await db.commit()

        file_paths: List[Path] = []
        for root, dirs, files in os.walk(directory_path):
            # Prune ignored directories in place
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                f_path = Path(root) / file
                if code_parser.is_parsable(str(f_path)):
                    file_paths.append(f_path)

        total_files = len(file_paths)
        total_chunks = 0

        for idx, file_path in enumerate(file_paths):
            try:
                rel_path = file_path.relative_to(directory_path).as_posix()
                content = file_path.read_text(encoding="utf-8", errors="replace")
                lines_count = len(content.splitlines())
                size_bytes = file_path.stat().st_size

                # Parse into AST or language-aware chunks
                parsed_chunks = code_parser.parse_file(rel_path, content)
                symbols = [c.symbol_name for c in parsed_chunks if c.symbol_name]

                # Save CodeFile record
                code_file = CodeFile(
                    repo_id=repo.id,
                    file_path=rel_path,
                    language=code_parser.get_language(rel_path),
                    size_bytes=size_bytes,
                    total_lines=lines_count,
                    symbols_summary=json.dumps(symbols[:20])
                )
                db.add(code_file)
                await db.flush()

                # Generate vector embeddings and save CodeChunks
                for p_chunk in parsed_chunks:
                    emb = await vector_store.generate_embedding(p_chunk.content)
                    chunk_record = CodeChunk(
                        repo_id=repo.id,
                        file_id=code_file.id,
                        chunk_index=p_chunk.chunk_index,
                        file_path=rel_path,
                        symbol_name=p_chunk.symbol_name,
                        symbol_type=p_chunk.symbol_type,
                        start_line=p_chunk.start_line,
                        end_line=p_chunk.end_line,
                        content=p_chunk.content,
                        embedding_json=json.dumps(emb)
                    )
                    db.add(chunk_record)
                    total_chunks += 1

                if progress_callback and total_files > 0:
                    pct = int(((idx + 1) / total_files) * 100)
                    await progress_callback(pct)

            except Exception as e:
                continue

        repo.status = "ready"
        repo.total_files = total_files
        repo.total_chunks = total_chunks
        await db.commit()

        return {"total_files": total_files, "total_chunks": total_chunks}

    async def clone_and_ingest(
        self,
        db: AsyncSession,
        repo: Repository,
        progress_callback=None
    ) -> Dict[str, int]:
        """Clone remote git repository or ingest local path."""
        target_dir = settings.REPOS_DIR / repo.name
        repo.status = "indexing"
        await db.commit()

        if repo.clone_url:
            # Clone from remote git url
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)

            cmd = ["git", "clone", "--depth", "1", "-b", repo.branch, repo.clone_url, str(target_dir)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                # If branch failed, try cloning default
                cmd_fallback = ["git", "clone", "--depth", "1", repo.clone_url, str(target_dir)]
                proc_fallback = subprocess.run(cmd_fallback, capture_output=True, text=True)
                if proc_fallback.returncode != 0:
                    repo.status = "error"
                    repo.error_message = proc_fallback.stderr or "Git clone failed"
                    await db.commit()
                    raise RuntimeError(f"Git clone error: {repo.error_message}")

            repo.local_path = str(target_dir)
            return await self.ingest_directory(db, repo, target_dir, progress_callback)
        elif repo.local_path and Path(repo.local_path).exists():
            return await self.ingest_directory(db, repo, Path(repo.local_path), progress_callback)
        else:
            repo.status = "error"
            repo.error_message = "No valid clone URL or local directory provided"
            await db.commit()
            raise ValueError(repo.error_message)


github_service = GitHubService()
