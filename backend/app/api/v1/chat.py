import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.llm_service import llm_service
from app.services.vector_store import vector_store

router = APIRouter(prefix="/chat", tags=["Streaming RAG Chat"])


class ChatRequest(BaseModel):
    repo_id: str
    query: str
    model: Optional[str] = "gemini-2.5-flash"


@router.post("/stream")
async def stream_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Server-Sent Events (SSE) Streaming Endpoint.
    Yields real-time step status, token-by-token synthesis, file citations, and latency metrics.
    """
    # 1. Search relevant chunks
    chunks = await vector_store.search_chunks(db, req.repo_id, req.query, top_k=5)

    async def event_generator():
        try:
            async for event in llm_service.stream_chat_response(req.query, chunks):
                payload = json.dumps(event)
                yield f"data: {payload}\n\n"
        except Exception as e:
            err_payload = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {err_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("")
async def standard_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Non-streaming synchronous chat endpoint."""
    chunks = await vector_store.search_chunks(db, req.repo_id, req.query, top_k=5)
    response_text = await llm_service.generate_response(
        system_prompt="You are DevPilot, an expert AI software engineering partner.",
        user_prompt=req.query,
        context_chunks=chunks,
        model=req.model
    )
    return {
        "query": req.query,
        "response": response_text,
        "sources": [
            {
                "file_path": c["file_path"],
                "symbol_name": c["symbol_name"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "score": c["score"]
            }
            for c in chunks
        ]
    }
