-- CockroachDB Migration: Add resolves_note_ids column to messages table
USE agent_memory;

ALTER TABLE messages ADD COLUMN IF NOT EXISTS resolves_note_ids TEXT[];
