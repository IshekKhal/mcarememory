-- CockroachDB Agent Memory Schema (Relational + Vector)
-- Enable vector index preview feature at cluster level
SET CLUSTER SETTING feature.vector_index.enabled = true;

CREATE DATABASE IF NOT EXISTS agent_memory;
USE agent_memory;

-- Safe updates setting required for vector index creation
SET sql_safe_updates = false;

-- 1. Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Messages table (Relational conversation history)
CREATE TABLE IF NOT EXISTS messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role STRING NOT NULL CHECK (role IN ('user', 'agent', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Task state table (In-flight agent task state persistence across node failures)
CREATE TABLE IF NOT EXISTS task_state (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    status STRING NOT NULL,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Memory embeddings table (Vector search storage for long-term agent memory)
CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    source_message_id UUID REFERENCES messages(message_id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- C-SPANN Vector Index for fast Approximate Nearest Neighbor (ANN) search
CREATE VECTOR INDEX IF NOT EXISTS idx_memory_embeddings ON memory_embeddings(embedding);
