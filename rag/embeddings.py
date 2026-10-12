"""
rag/embeddings.py - Gemini Vector Embedding Generation
"""

import os
from typing import List, Optional
from google import genai
from google.genai import types

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from llm_provider import get_gemini_api_key

DEFAULT_EMBEDDING_MODEL = "gemini-embedding-2"
DEFAULT_EMBEDDING_DIM = 768


def get_embedding(
    text: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
    dimension: int = DEFAULT_EMBEDDING_DIM,
    client: Optional[genai.Client] = None
) -> List[float]:
    """
    Generates a dense vector embedding using Google Gemini API.
    Configures output_dimensionality (e.g. 768) to ensure compatibility
    with pgvector HNSW indexing (limits <= 2000 dimensions).
    """
    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty or whitespace text.")

    if client is None:
        api_key = get_gemini_api_key()
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured in environment.")
        client = genai.Client(api_key=api_key)

    config = types.EmbedContentConfig(output_dimensionality=dimension)
    response = client.models.embed_content(
        model=model,
        contents=text.strip(),
        config=config
    )
    
    if not response.embeddings or not response.embeddings[0].values:
        raise RuntimeError("Embedding API returned empty embedding vector.")

    return response.embeddings[0].values
