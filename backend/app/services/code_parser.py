import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".sql": "sql",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
}

IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".next", "dist", "build", ".mypy_cache"
}


@dataclass
class ParsedChunk:
    chunk_index: int
    file_path: str
    symbol_name: str
    symbol_type: str  # function, class, module_header, code_block, interface
    start_line: int
    end_line: int
    content: str
    language: str


class CodeParser:
    """Intelligent AST and syntax-aware multi-language code chunker."""

    def is_parsable(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in SUPPORTED_EXTENSIONS

    def get_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return SUPPORTED_EXTENSIONS.get(ext, "unknown")

    def parse_python(self, file_path: str, source_code: str) -> List[ParsedChunk]:
        """Use Python standard library AST for high-fidelity structural parsing."""
        chunks: List[ParsedChunk] = []
        lines = source_code.splitlines()

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            # Fallback to generic line chunker if file has syntax errors
            return self.parse_generic(file_path, source_code, "python")

        chunk_idx = 0

        # 1. Capture module-level imports and docstrings
        last_header_line = 0
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.Expr)):
                end = getattr(node, "end_lineno", node.lineno)
                last_header_line = max(last_header_line, end)

        if last_header_line > 0:
            header_content = "\n".join(lines[:last_header_line])
            if header_content.strip():
                chunks.append(ParsedChunk(
                    chunk_index=chunk_idx,
                    file_path=file_path,
                    symbol_name="module_header",
                    symbol_type="module_header",
                    start_line=1,
                    end_line=last_header_line,
                    content=header_content,
                    language="python"
                ))
                chunk_idx += 1

        # 2. Iterate AST top-level classes and functions
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                class_content = "\n".join(lines[start - 1:end])
                chunks.append(ParsedChunk(
                    chunk_index=chunk_idx,
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="class",
                    start_line=start,
                    end_line=end,
                    content=class_content,
                    language="python"
                ))
                chunk_idx += 1

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                fn_content = "\n".join(lines[start - 1:end])
                chunks.append(ParsedChunk(
                    chunk_index=chunk_idx,
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="function",
                    start_line=start,
                    end_line=end,
                    content=fn_content,
                    language="python"
                ))
                chunk_idx += 1

        # If no AST symbols found (e.g. script statements), chunk as full or block
        if not chunks:
            return self.parse_generic(file_path, source_code, "python")

        return chunks

    def parse_structural(self, file_path: str, source_code: str, language: str) -> List[ParsedChunk]:
        """Language-aware structural parsing for JS/TS, Go, Rust, Java using signature boundary tracking."""
        lines = source_code.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return []

        # Patterns per language
        patterns = {
            "javascript": [
                (r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)", "function"),
                (r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", "function"),
                (r"(?:export\s+)?class\s+([A-Za-z0-9_$]+)", "class"),
            ],
            "typescript": [
                (r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)", "function"),
                (r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", "function"),
                (r"(?:export\s+)?class\s+([A-Za-z0-9_$]+)", "class"),
                (r"(?:export\s+)?interface\s+([A-Za-z0-9_$]+)", "interface"),
                (r"(?:export\s+)?type\s+([A-Za-z0-9_$]+)\s*=", "type_definition"),
            ],
            "go": [
                (r"func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)\s*\(", "function"),
                (r"type\s+([A-Za-z0-9_]+)\s+(?:struct|interface)", "type_definition"),
            ],
            "rust": [
                (r"(?:pub\s+)?fn\s+([A-Za-z0-9_]+)", "function"),
                (r"(?:pub\s+)?(?:struct|enum|trait)\s+([A-Za-z0-9_]+)", "type_definition"),
                (r"impl(?:\s+<[^>]+>)?\s+([A-Za-z0-9_]+)", "implementation"),
            ],
            "java": [
                (r"(?:public|protected|private)?\s*(?:static\s+)?(?:class|interface|enum)\s+([A-Za-z0-9_]+)", "class"),
                (r"(?:public|protected|private)\s+(?:static\s+)?(?:[\w<>\[\], ]+)\s+([A-Za-z0-9_]+)\s*\([^)]*\)", "function"),
            ],
        }

        lang_patterns = patterns.get(language, [])
        if not lang_patterns:
            return self.parse_generic(file_path, source_code, language)

        # Detect symbols and line offsets
        detected_symbols = []
        for line_num, line in enumerate(lines, start=1):
            line_str = line.strip()
            if line_str.startswith("//") or line_str.startswith("/*") or line_str.startswith("*"):
                continue
            for pat, sym_type in lang_patterns:
                m = re.search(pat, line)
                if m:
                    detected_symbols.append((line_num, m.group(1), sym_type))
                    break

        if not detected_symbols:
            return self.parse_generic(file_path, source_code, language)

        chunks: List[ParsedChunk] = []
        chunk_idx = 0

        # Optional header block if code exists before first symbol
        first_line = detected_symbols[0][0]
        if first_line > 1:
            header_content = "\n".join(lines[:first_line - 1]).strip()
            if header_content:
                chunks.append(ParsedChunk(
                    chunk_index=chunk_idx,
                    file_path=file_path,
                    symbol_name="module_header",
                    symbol_type="module_header",
                    start_line=1,
                    end_line=first_line - 1,
                    content=header_content,
                    language=language
                ))
                chunk_idx += 1

        for i, (start_line, sym_name, sym_type) in enumerate(detected_symbols):
            if i < len(detected_symbols) - 1:
                end_line = detected_symbols[i + 1][0] - 1
            else:
                end_line = total_lines

            content = "\n".join(lines[start_line - 1:end_line]).strip()
            if content:
                chunks.append(ParsedChunk(
                    chunk_index=chunk_idx,
                    file_path=file_path,
                    symbol_name=sym_name,
                    symbol_type=sym_type,
                    start_line=start_line,
                    end_line=end_line,
                    content=content,
                    language=language
                ))
                chunk_idx += 1

        return chunks

    def parse_generic(self, file_path: str, source_code: str, language: str, chunk_size: int = 50) -> List[ParsedChunk]:
        """Language-agnostic chunker preserving logical lines and overlap."""
        chunks: List[ParsedChunk] = []
        lines = source_code.splitlines()
        total_lines = len(lines)

        if total_lines == 0:
            return []

        if total_lines <= chunk_size:
            return [
                ParsedChunk(
                    chunk_index=0,
                    file_path=file_path,
                    symbol_name="main",
                    symbol_type="code_block",
                    start_line=1,
                    end_line=total_lines,
                    content=source_code,
                    language=language
                )
            ]

        overlap = 10
        step = chunk_size - overlap
        chunk_idx = 0

        for i in range(0, total_lines, step):
            start = i + 1
            end = min(i + chunk_size, total_lines)
            chunk_text = "\n".join(lines[i:end])

            symbol_name = f"block_{start}_{end}"
            match = re.search(r"(?:class|function|def|func|interface|type)\s+([A-Za-z0-9_]+)", chunk_text)
            if match:
                symbol_name = match.group(1)

            chunks.append(ParsedChunk(
                chunk_index=chunk_idx,
                file_path=file_path,
                symbol_name=symbol_name,
                symbol_type="code_block",
                start_line=start,
                end_line=end,
                content=chunk_text,
                language=language
            ))
            chunk_idx += 1
            if end >= total_lines:
                break

        return chunks

    def parse_file(self, file_path: str, content: str) -> List[ParsedChunk]:
        language = self.get_language(file_path)
        if language == "python":
            return self.parse_python(file_path, content)
        elif language in ["javascript", "typescript", "go", "rust", "java"]:
            return self.parse_structural(file_path, content, language)
        return self.parse_generic(file_path, content, language)


code_parser = CodeParser()
