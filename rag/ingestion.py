"""
rag/ingestion.py - Document Text Ingestion, Chunking, and pgvector Storage
"""

import os
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from db import execute_query, execute_single, execute_statement, get_connection
from rag.embeddings import get_embedding, DEFAULT_EMBEDDING_MODEL, DEFAULT_EMBEDDING_DIM


def compute_file_hash(content: bytes) -> str:
    """Computes SHA-256 hash of binary content to detect duplicates and track file changes."""
    return hashlib.sha256(content).hexdigest()


def extract_text_from_file(filepath: str) -> List[Tuple[int, str]]:
    """
    Extracts text from supported document types (.txt, .md, .pdf).
    Returns list of (page_number, text) tuples. Page number is 1-indexed for PDF, or 1 for text files.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Document file not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    if ext in (".txt", ".md"):
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return [(1, text)]

    elif ext == ".pdf":
        if not PYPDF_AVAILABLE:
            raise RuntimeError("pypdf is required to extract text from PDF documents.")
        pages_content = []
        reader = PdfReader(filepath)
        for page_idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages_content.append((page_idx, page_text.strip()))
        if not pages_content:
            raise ValueError(f"No extractable text found in PDF document: {filepath}")
        return pages_content

    else:
        raise ValueError(f"Unsupported document format: '{ext}'. Supported formats: .txt, .md, .pdf")


def split_text_into_chunks(
    text: str,
    page_number: int = 1,
    max_chunk_size: int = 500,
    overlap: int = 60
) -> List[Dict[str, Any]]:
    """
    Splits text into semantically cohesive, overlapping chunks.
    Prefers splitting on paragraphs or double newlines, falling back to sentences.
    """
    cleaned_text = text.replace("\r\n", "\n").strip()
    if not cleaned_text:
        return []

    # First split by double newlines into natural paragraphs
    paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
    
    raw_sections = []
    for para in paragraphs:
        if len(para) <= max_chunk_size:
            raw_sections.append(para)
        else:
            # Split longer paragraphs by lines or sentences
            lines = [l.strip() for l in para.split("\n") if l.strip()]
            current = []
            current_len = 0
            for line in lines:
                if current_len + len(line) + 1 <= max_chunk_size:
                    current.append(line)
                    current_len += len(line) + 1
                else:
                    if current:
                        raw_sections.append(" ".join(current))
                    current = [line]
                    current_len = len(line)
            if current:
                raw_sections.append(" ".join(current))

    # Assemble sections into overlapping chunks
    chunks = []
    current_chunk = ""

    for sec in raw_sections:
        if not current_chunk:
            current_chunk = sec
        elif len(current_chunk) + len(sec) + 2 <= max_chunk_size:
            current_chunk += "\n\n" + sec
        else:
            chunks.append(current_chunk)
            # Create overlap from end of current chunk
            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
            current_chunk = overlap_text + "\n\n" + sec

    if current_chunk and (not chunks or current_chunk != chunks[-1]):
        chunks.append(current_chunk)

    chunk_dicts = []
    for idx, c_text in enumerate(chunks):
        chunk_dicts.append({
            "chunk_index": idx,
            "page_number": page_number,
            "text": c_text.strip()
        })

    return chunk_dicts


def ingest_document(
    filepath: Optional[str] = None,
    raw_content: Optional[str] = None,
    title: Optional[str] = None,
    document_type: str = "sop",
    version: str = "1.0",
    effective_date: Optional[str] = None,
    restaurant_id: str = "default_restaurant",
    data_origin: str = "SYNTHETIC",
    force_reprocess: bool = False
) -> Dict[str, Any]:
    """
    Ingests a document into Supabase PostgreSQL documents and document_chunks tables with pgvector embeddings.
    
    Prevents duplicate ingestion using SHA-256 content hashes.
    Enforces atomic transaction: if embedding or insertion fails, the document is not marked as indexed.
    """
    if filepath:
        if not title:
            title = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            file_bytes = f.read()
        file_hash = compute_file_hash(file_bytes)
        pages_content = extract_text_from_file(filepath)
        full_body = "\n\n".join([text for _, text in pages_content])
    elif raw_content:
        if not title:
            raise ValueError("title must be provided when ingesting raw_content.")
        file_bytes = raw_content.encode("utf-8")
        file_hash = compute_file_hash(file_bytes)
        pages_content = [(1, raw_content)]
        full_body = raw_content
    else:
        raise ValueError("Either filepath or raw_content must be provided.")

    eff_date = effective_date or date.today().isoformat()

    # Check for existing document with same title / hash
    existing = execute_single(
        """
        SELECT document_id, file_hash, status 
        FROM documents 
        WHERE (file_hash = %s OR title = %s) AND restaurant_id = %s;
        """,
        (file_hash, title, restaurant_id)
    )

    if existing and not force_reprocess and existing.get("file_hash") == file_hash and existing.get("status") == "indexed":
        # Check if chunks already exist with embeddings
        chunk_count_row = execute_single(
            "SELECT COUNT(*) as cnt FROM document_chunks WHERE document_id = %s AND embedding IS NOT NULL;",
            (existing["document_id"],)
        )
        if chunk_count_row and chunk_count_row.get("cnt", 0) > 0:
            return {
                "status": "already_indexed",
                "document_id": existing["document_id"],
                "title": title,
                "message": f"Document '{title}' is already indexed with up-to-date content hash.",
                "chunks_count": chunk_count_row.get("cnt", 0),
                "data_origin": data_origin
            }

    # Generate document ID if new, or reuse existing
    doc_id = existing["document_id"] if existing else f"DOC_{hashlib.md5(title.encode()).hexdigest()[:8].upper()}"

    # Split pages into chunks
    all_chunks: List[Dict[str, Any]] = []
    chunk_counter = 0
    for page_num, p_text in pages_content:
        page_chunks = split_text_into_chunks(p_text, page_number=page_num)
        for pc in page_chunks:
            all_chunks.append({
                "chunk_id": f"{doc_id}_CH{chunk_counter:04d}",
                "chunk_index": chunk_counter,
                "page_number": page_num,
                "chunk_text": pc["text"]
            })
            chunk_counter += 1

    if not all_chunks:
        raise ValueError(f"No text chunks generated for document '{title}'.")

    # Generate embeddings for each chunk before committing database transaction
    embedded_chunks = []
    for c in all_chunks:
        try:
            vec = get_embedding(c["chunk_text"], model=DEFAULT_EMBEDDING_MODEL, dimension=DEFAULT_EMBEDDING_DIM)
            vec_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
            c["vector_str"] = vec_str
            embedded_chunks.append(c)
        except Exception as embed_err:
            raise RuntimeError(f"Embedding generation failed for chunk {c['chunk_id']}: {str(embed_err)}")

    # Atomic DB Insertion
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Upsert document record
            cur.execute(
                """
                INSERT INTO documents (
                    document_id, title, document_type, version, effective_date, body, 
                    data_origin, file_hash, restaurant_id, status, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'indexed', CURRENT_TIMESTAMP)
                ON CONFLICT (document_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    document_type = EXCLUDED.document_type,
                    version = EXCLUDED.version,
                    effective_date = EXCLUDED.effective_date,
                    body = EXCLUDED.body,
                    file_hash = EXCLUDED.file_hash,
                    status = 'indexed',
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (doc_id, title, document_type, version, eff_date, full_body, data_origin, file_hash, restaurant_id)
            )

            # 2. Remove any previous chunks for this document
            cur.execute("DELETE FROM document_chunks WHERE document_id = %s;", (doc_id,))

            # 3. Insert new chunks with vector embeddings
            for ec in embedded_chunks:
                cur.execute(
                    """
                    INSERT INTO document_chunks (
                        chunk_id, document_id, chunk_index, chunk_text, source_title, 
                        source_version, embedding_status, data_origin, embedding, 
                        embedding_model, page_number, restaurant_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'GENERATED', %s, %s::vector, %s, %s, %s);
                    """,
                    (
                        ec["chunk_id"], doc_id, ec["chunk_index"], ec["chunk_text"],
                        title, version, data_origin, ec["vector_str"],
                        DEFAULT_EMBEDDING_MODEL, ec["page_number"], restaurant_id
                    )
                )

            conn.commit()

    return {
        "status": "success",
        "document_id": doc_id,
        "title": title,
        "chunks_indexed": len(embedded_chunks),
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "embedding_dimension": DEFAULT_EMBEDDING_DIM,
        "restaurant_id": restaurant_id,
        "data_origin": data_origin
    }


def migrate_existing_documents() -> Dict[str, Any]:
    """
    Backfills embeddings for pre-existing documents (e.g. DOC001-DOC004 in synthetic schema)
    and ingests local knowledge documents (rag/documents/cafe_sop.txt).
    """
    results = {
        "pre_existing_chunks_embedded": 0,
        "local_docs_ingested": 0,
        "errors": []
    }

    # 1. Check for un-embedded chunks in database
    unembedded = execute_query(
        "SELECT chunk_id, chunk_text FROM document_chunks WHERE embedding IS NULL;"
    )

    for ch in unembedded:
        try:
            vec = get_embedding(ch["chunk_text"])
            vec_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE document_chunks 
                        SET embedding = %s::vector,
                            embedding_status = 'GENERATED',
                            embedding_model = %s
                        WHERE chunk_id = %s;
                        """,
                        (vec_str, DEFAULT_EMBEDDING_MODEL, ch["chunk_id"])
                    )
                    conn.commit()
            results["pre_existing_chunks_embedded"] += 1
        except Exception as e:
            results["errors"].append(f"Failed embedding chunk {ch['chunk_id']}: {str(e)}")

    # 2. Ingest local cafe_sop.txt
    local_sop_path = os.path.join(os.path.dirname(__file__), "documents", "cafe_sop.txt")
    if os.path.exists(local_sop_path):
        try:
            res = ingest_document(
                filepath=local_sop_path,
                title="Cafe Operations Standard Operating Procedures (SOP)",
                document_type="sop",
                version="1.0",
                restaurant_id="default_restaurant",
                data_origin="SYNTHETIC"
            )
            if res.get("status") in ("success", "already_indexed"):
                results["local_docs_ingested"] += 1
        except Exception as e:
            results["errors"].append(f"Failed ingesting local cafe_sop.txt: {str(e)}")

    return results
