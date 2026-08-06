-- CockroachDB Migration: Add caregiver_name and note_type to messages table
USE agent_memory;

ALTER TABLE messages ADD COLUMN IF NOT EXISTS caregiver_name STRING;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS note_type STRING DEFAULT 'general';
