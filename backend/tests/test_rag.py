import pytest
from app.services.vector_store import vector_store


@pytest.mark.asyncio
async def test_embedding_generation():
    text = "Authentication and JWT tokens"
    emb = await vector_store.generate_embedding(text)
    assert isinstance(emb, list)
    assert len(emb) == 768
    # Should be normalized
    import numpy as np
    norm = np.linalg.norm(np.array(emb))
    assert abs(norm - 1.0) < 1e-3


def test_lexical_overlap():
    query = "refresh token error"
    match_text = "Handling expired refresh token exceptions in auth middleware"
    no_match = "Database connection pool initialization"

    score_match = vector_store._lexical_score(query, match_text)
    score_no_match = vector_store._lexical_score(query, no_match)

    assert score_match > score_no_match
    assert score_match >= 0.6
