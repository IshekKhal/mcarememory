-- CockroachDB Migration: Resize embeddings column from 1536 to 1024 dimensions (Amazon Titan Text Embeddings V2)
USE agent_memory;

-- Safe updates setting required for vector index operations
SET sql_safe_updates = false;

-- Drop existing vector index and memory_embeddings table
DROP INDEX IF EXISTS idx_memory_embeddings;
DROP TABLE IF EXISTS memory_embeddings;

-- Recreate memory_embeddings table with VECTOR(1024)
CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    source_message_id UUID REFERENCES messages(message_id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Recreate C-SPANN Vector Index for fast Approximate Nearest Neighbor (ANN) search
CREATE VECTOR INDEX IF NOT EXISTS idx_memory_embeddings ON memory_embeddings(embedding);
