"""
rag/rag.py - Complete RAG Pipeline backed by Supabase pgvector
"""

import os
from typing import List, Tuple, Dict, Any, Optional
from google import genai

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from rag.embeddings import get_embedding, DEFAULT_EMBEDDING_MODEL, DEFAULT_EMBEDDING_DIM
from rag.ingestion import ingest_document, split_text_into_chunks
from rag.retrieval import search_restaurant_knowledge
from llm_provider import (
    get_gemini_api_key,
    DEFAULT_GENERATION_MODEL,
    classify_llm_error,
    QuotaExhaustedError
)

def get_genai_client() -> Optional[genai.Client]:
    """Retrieves or creates a genai Client using centralized API key loader."""
    api_key = get_gemini_api_key()
    return genai.Client(api_key=api_key) if api_key else None

EMBEDDING_MODEL = DEFAULT_EMBEDDING_MODEL
GENERATION_MODELS = [DEFAULT_GENERATION_MODEL, "gemini-3.7-flash", "gemini-3.5-flash", "gemini-flash-latest"]


def create_chunks(filepath: str) -> List[str]:
    """
    Backwards-compatible chunk creator for local text files.
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as file:
        content = file.read()
    raw_chunks = content.split("\n\n")
    return [chunk.strip() for chunk in raw_chunks if chunk.strip()]


def retrieve(query: str, top_k: int = 3) -> List[Tuple[str, float]]:
    """
    The main RAG Retrieval function backed by Supabase pgvector semantic search.
    Queries document_chunks with cosine distance matching and returns top_k (chunk_text, similarity) tuples.
    """
    res = search_restaurant_knowledge(query, top_k=top_k)
    if res.get("status") == "success":
        return [(r["chunk_text"], r["similarity"]) for r in res.get("results", [])]
    elif res.get("status") == "no_results":
        return []
    else:
        raise RuntimeError(res.get("message", "Database pgvector retrieval failed."))


def answer_with_rag(query: str) -> str:
    """
    Executes grounded RAG generation:
      1. Semantic retrieval from Supabase pgvector.
      2. Context assembly with source citations.
      3. Grounded Gemini synthesis strictly adhering to retrieved evidence.
    """
    search_res = search_restaurant_knowledge(query, top_k=3)

    if search_res.get("status") == "no_results" or not search_res.get("results"):
        return "The available documents do not contain enough information to answer this question."

    if search_res.get("status") == "error":
        return f"Error retrieving knowledge: {search_res.get('message')}"

    results = search_res.get("results", [])
    context_blocks = [
        f"Source: {r['citation']}\n{r['chunk_text']}"
        for r in results
    ]
    context_text = "\n\n".join(context_blocks)

    prompt = f"""You are an assistant answering questions using cafe standard operating procedures (SOP).
Answer the user's question using ONLY the supplied context below.
Strict Rules:
1. Answer using ONLY the supplied context.
2. Do NOT invent, speculate, or extrapolate information.
3. If the answer cannot be found in the context, explicitly say: "The available documents do not contain enough information to answer this question."
4. Include source citations (e.g. [Document Title, Chunk #]) when making claims.
5. Keep the answer concise.

CONTEXT:
{context_text}

QUESTION:
{query}

ANSWER:"""

    client = get_genai_client()
    if not client:
        return "Gemini API client is not configured on the server."

    answer = "No response generated."
    last_error = None
    for model_name in GENERATION_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if response.text:
                answer = response.text.strip()
                break
        except Exception as e:
            classified = classify_llm_error(e)
            last_error = classified
            if isinstance(classified, QuotaExhaustedError):
                return "Gemini request quota has been exhausted. Please wait for daily quota reset or configure a paid API tier."
            continue

    if answer == "No response generated." and last_error:
        return f"Error generating answer: {str(last_error)}"

    return answer


if __name__ == "__main__":
    print("=" * 60)
    print("TESTING PGVECTOR RETRIEVAL")
    print("=" * 60)
    q = "What are the rules for storing milk?"
    res = retrieve(q, top_k=3)
    for c_text, score in res:
        print(f"Similarity: {score:.4f} | {c_text[:80]}...")
    print("\n" + "=" * 60)
    print("TESTING GROUNDED ANSWER GENERATION")
    print("=" * 60)
    print(answer_with_rag(q))
