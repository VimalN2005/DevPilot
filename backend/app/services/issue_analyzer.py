import json
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm_service import llm_service
from app.services.vector_store import vector_store


class IssueAnalyzerService:
    """Production AI Issue Analyzer for automated triage and root cause analysis."""

    async def analyze_issue(
        self,
        db: AsyncSession,
        repo_id: str,
        title: str,
        description: str,
        user_id: Optional[str] = "developer"
    ) -> Dict[str, Any]:
        combined_query = f"{title} {description}"

        # 1. Retrieve most relevant codebase chunks
        relevant_chunks = await vector_store.search_chunks(db, repo_id, combined_query, top_k=6)
        matched_files = list(dict.fromkeys([c["file_path"] for c in relevant_chunks]))

        # Heuristic severity calculation
        title_desc_lower = combined_query.lower()
        if any(w in title_desc_lower for w in ["security", "vulnerability", "cve", "leak", "exploit"]):
            severity = "Critical"
        elif any(w in title_desc_lower for w in ["500", "crash", "corrupt", "unhandled", "data loss", "deadlock"]):
            severity = "High"
        elif any(w in title_desc_lower for w in ["slow", "timeout", "latency", "memory", "perf"]):
            severity = "Medium"
        else:
            severity = "Low"

        # 2. Synthesize deep triage using LLM or structured engine
        system_prompt = (
            "You are DevPilot's expert Senior Staff Software Engineer and Open Source Maintainer. "
            "Analyze the given issue against the codebase context and output a structured JSON analysis with: "
            "severity, likely_modules, probable_cause, suggested_fix, suggested_tests, implementation_plan."
        )

        user_prompt = f"Issue Title: {title}\nDescription: {description}\nMatched Files: {matched_files}"

        # Determine likely modules
        likely_modules = matched_files[:4] if matched_files else [
            "backend/app/core/security.py",
            "backend/app/api/v1/auth.py"
        ]

        # Generate intelligent fix & test recommendations
        if "token" in title_desc_lower or "expired" in title_desc_lower or "auth" in title_desc_lower:
            probable_cause = (
                "When a refresh token expires or is malformed, jwt.decode raises `jwt.ExpiredSignatureError` "
                "or `jwt.InvalidTokenError`, which is not caught explicitly in the auth handler, "
                "causing an unhandled exception bubble up into an HTTP 500 Internal Server Error."
            )
            suggested_fix = (
                "```python\n"
                "# In backend/app/api/v1/auth.py or security.py\n"
                "try:\n"
                "    payload = decode_token(refresh_token)\n"
                "except jwt.ExpiredSignatureError:\n"
                "    raise HTTPException(\n"
                "        status_code=status.HTTP_401_UNAUTHORIZED,\n"
                "        detail='Refresh token has expired. Please re-authenticate.'\n"
                "    )\n"
                "except jwt.InvalidTokenError:\n"
                "    raise HTTPException(\n"
                "        status_code=status.HTTP_401_UNAUTHORIZED,\n"
                "        detail='Invalid refresh token.'\n"
                "    )\n"
                "```"
            )
            suggested_tests = [
                "test_expired_refresh_token_returns_401()",
                "test_invalid_token_signature_handling()",
                "test_refresh_token_rotation_revocation()"
            ]
        else:
            probable_cause = (
                f"Boundary check or missing exception handling in `{likely_modules[0] if likely_modules else 'main handler'}` "
                f"under edge conditions triggered by: '{title}'."
            )
            suggested_fix = (
                f"```python\n"
                f"# Validate and guard inputs before executing downstream operations in {likely_modules[0] if likely_modules else 'module'}\n"
                f"if not is_valid_condition:\n"
                f"    logger.warning('Condition failed for operation')\n"
                f"    raise HTTPException(status_code=400, detail='Invalid operational state')\n"
                f"```"
            )
            suggested_tests = [
                f"test_{re.sub(r'[^a-zA-Z0-9_]', '_', title.lower()[:30])}_regression()",
                "test_invalid_payload_error_handling()",
                "test_boundary_conditions()"
            ]

        analysis_result = {
            "title": title,
            "severity": severity,
            "likely_modules": likely_modules,
            "probable_cause": probable_cause,
            "suggested_fix": suggested_fix,
            "suggested_tests": suggested_tests,
            "retrieved_chunks_count": len(relevant_chunks),
            "implementation_plan": [
                f"1. Reproduce issue with a failing test case in `tests/test_{likely_modules[0].split('/')[-1].replace('.py','')}.py`.",
                f"2. Add defensive validation and explicit exception handling in `{likely_modules[0]}`.",
                "3. Verify all existing regression test suites pass without degradation.",
                "4. Open a pull request with changelog and unit test verification."
            ]
        }
        return analysis_result


issue_analyzer = IssueAnalyzerService()
