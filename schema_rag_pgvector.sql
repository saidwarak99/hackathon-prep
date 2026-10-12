-- schema_rag_pgvector.sql
-- Migration: Enable pgvector and add vector columns, metadata, and indexes to documents and document_chunks

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Extend documents table for ingestion tracking and dataset/restaurant isolation
ALTER TABLE documents 
  ADD COLUMN IF NOT EXISTS file_hash TEXT,
  ADD COLUMN IF NOT EXISTS restaurant_id TEXT NOT NULL DEFAULT 'default_restaurant',
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'indexed',
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- 3. Extend document_chunks table with 768-dimensional vector embedding, model metadata, and page tracking
ALTER TABLE document_chunks 
  ADD COLUMN IF NOT EXISTS embedding vector(768),
  ADD COLUMN IF NOT EXISTS embedding_model TEXT DEFAULT 'gemini-embedding-2',
  ADD COLUMN IF NOT EXISTS page_number INTEGER,
  ADD COLUMN IF NOT EXISTS restaurant_id TEXT NOT NULL DEFAULT 'default_restaurant',
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- 4. Create performance indexes
CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_restaurant ON documents(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_restaurant ON document_chunks(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_chunk ON document_chunks(document_id, chunk_index);

-- 5. Create HNSW vector similarity index using cosine distance (vector_cosine_ops)
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);
