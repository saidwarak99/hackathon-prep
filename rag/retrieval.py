"""
rag/retrieval.py - Semantic Knowledge Retrieval using Supabase pgvector
"""

from typing import Dict, Any, List, Optional
from db import execute_query
from rag.embeddings import get_embedding, DEFAULT_EMBEDDING_MODEL, DEFAULT_EMBEDDING_DIM


def search_restaurant_knowledge(
    query: str,
    top_k: int = 3,
    restaurant_id: str = "default_restaurant",
    similarity_threshold: float = 0.50
) -> Dict[str, Any]:
    """
    Performs cosine-similarity semantic retrieval across restaurant SOPs,
    policies, and operational knowledge stored in Supabase pgvector.

    Parameters:
        query (str): Natural language inquiry or search phrase.
        top_k (int): Maximum number of top matching chunks to retrieve (1-10, default: 3).
        restaurant_id (str): Tenant / restaurant identifier for dataset isolation.
        similarity_threshold (float): Minimum cosine similarity cutoff (0.0 - 1.0, default: 0.50).

    Returns:
        Dict[str, Any]: Structured search results with citations and similarity scores.
    """
    if not query or not query.strip():
        return {
            "status": "error",
            "message": "Search query cannot be empty or whitespace only."
        }

    clamped_k = max(1, min(int(top_k), 10))

    try:
        # 1. Generate query embedding with identical model and dimensionality
        query_vector = get_embedding(
            query.strip(),
            model=DEFAULT_EMBEDDING_MODEL,
            dimension=DEFAULT_EMBEDDING_DIM
        )
        vec_str = "[" + ",".join(f"{x:.6f}" for x in query_vector) + "]"

        # 2. Query pgvector cosine distance: (1 - cosine_distance) = cosine_similarity
        sql = """
            SELECT 
                dc.chunk_id,
                dc.document_id,
                dc.chunk_index,
                dc.page_number,
                dc.chunk_text,
                dc.source_title,
                dc.source_version,
                d.effective_date::text as effective_date,
                d.document_type,
                d.data_origin,
                ROUND((1 - (dc.embedding <=> %s::vector))::numeric, 4) as similarity
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.document_id
            WHERE dc.restaurant_id = %s
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> %s::vector ASC
            LIMIT %s;
        """
        rows = execute_query(sql, (vec_str, restaurant_id, vec_str, clamped_k))

        if not rows:
            return {
                "status": "no_results",
                "query": query,
                "message": "No restaurant knowledge documents currently indexed in database.",
                "total_results": 0,
                "retrieved_chunks": [],
                "results": [],
                "citations": [],
                "data_origin": "SYNTHETIC"
            }

        # 3. Filter by similarity threshold
        passing_results = []
        for r in rows:
            sim = float(r["similarity"])
            if sim >= similarity_threshold:
                page_info = f", Page {r['page_number']}" if r.get("page_number") and r["page_number"] > 1 else ""
                citation = f"[{r['source_title']} v{r['source_version']}, Chunk {r['chunk_index']}{page_info}]"
                passing_results.append({
                    "chunk_id": r["chunk_id"],
                    "document_id": r["document_id"],
                    "source_title": r["source_title"],
                    "source_version": r["source_version"],
                    "chunk_index": r["chunk_index"],
                    "page_number": r.get("page_number") or 1,
                    "chunk_text": r["chunk_text"],
                    "similarity": sim,
                    "citation": citation,
                    "effective_date": r["effective_date"],
                    "document_type": r["document_type"],
                    "data_origin": r["data_origin"]
                })

        if not passing_results:
            top_sim = float(rows[0]["similarity"]) if rows else 0.0
            return {
                "status": "no_results",
                "query": query,
                "message": (
                    f"No relevant restaurant knowledge or policy documents found matching the inquiry. "
                    f"Top available match had insufficient similarity score ({top_sim:.2f} < threshold {similarity_threshold:.2f})."
                ),
                "total_results": 0,
                "retrieved_chunks": [],
                "results": [],
                "citations": [],
                "data_origin": "SYNTHETIC"
            }

        return {
            "status": "success",
            "query": query,
            "total_results": len(passing_results),
            "retrieved_chunks": [pr["chunk_text"] for pr in passing_results],
            "results": passing_results,
            "citations": [pr["citation"] for pr in passing_results],
            "data_origin": "SYNTHETIC"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database pgvector semantic search failed: {str(e)}"
        }
