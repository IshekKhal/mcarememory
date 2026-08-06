import logging
import psycopg
from app.config import COCKROACH_URL
from app.embeddings import generate_embedding

logger = logging.getLogger(__name__)

def get_connection():
    """Returns a psycopg connection to CockroachDB."""
    return psycopg.connect(COCKROACH_URL)

def create_conversation(agent_id: str = "caregiver_assistant") -> str:
    """
    Creates a new conversation record in CockroachDB.
    
    Args:
        agent_id (str): Identifier for the agent managing the conversation.
        
    Returns:
        str: Created conversation_id (UUID string).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (agent_id)
                VALUES (%s)
                RETURNING conversation_id;
                """,
                (agent_id,)
            )
            row = cur.fetchone()
            conn.commit()
            return str(row[0])

def add_caregiver_note(
    conversation_id: str,
    caregiver_name: str,
    content: str,
    note_type: str = "general"
) -> str:
    """
    Inserts a caregiver's note into the messages table, computes a 1024-dim vector
    embedding for the content, and stores the vector in memory_embeddings.
    
    Args:
        conversation_id (str): UUID string of the active conversation.
        caregiver_name (str): Name or role of the caregiver entering the note.
        content (str): Text body of the caregiver note.
        note_type (str): Category (e.g. 'medication', 'observation', 'appointment', 'general').
        
    Returns:
        str: Created message_id (UUID string).
    """
    if not content or not content.strip():
        raise ValueError("Caregiver note content cannot be empty.")
    if not caregiver_name or not caregiver_name.strip():
        raise ValueError("Caregiver name cannot be empty.")

    # 1. Generate real embedding via SageMaker BGE-large-en-v1.5
    embedding_vector = generate_embedding(content)
    embedding_str = f"[{','.join(str(f) for f in embedding_vector)}]"

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 2. Insert into messages table
            cur.execute(
                """
                INSERT INTO messages (conversation_id, role, content, caregiver_name, note_type)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING message_id;
                """,
                (conversation_id, "user", content, caregiver_name, note_type)
            )
            message_row = cur.fetchone()
            message_id = str(message_row[0])

            # 3. Insert embedding into memory_embeddings table
            cur.execute(
                """
                INSERT INTO memory_embeddings (conversation_id, source_message_id, content, embedding)
                VALUES (%s, %s, %s, %s::vector);
                """,
                (conversation_id, message_id, content, embedding_str)
            )

            conn.commit()
            logger.info(f"Added caregiver note [{message_id}] by '{caregiver_name}' ({note_type})")
            return message_id

def recall_relevant_notes(
    conversation_id: str,
    question: str,
    k: int = 5
) -> list[dict]:
    """
    Given a question, generates its embedding, queries CockroachDB for the top-k nearest
    embedding matches scoped to conversation_id, and returns matching notes with metadata.
    
    Args:
        conversation_id (str): UUID string of the target conversation.
        question (str): The search query or question text.
        k (int): Number of top matches to retrieve.
        
    Returns:
        list[dict]: List of matching note dicts containing memory_id, content, caregiver_name,
                    note_type, created_at, and distance score.
    """
    if not question or not question.strip():
        raise ValueError("Search question cannot be empty.")

    # Generate query embedding
    query_vector = generate_embedding(question)
    query_vector_str = f"[{','.join(str(f) for f in query_vector)}]"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    e.memory_id,
                    e.content,
                    m.caregiver_name,
                    m.note_type,
                    m.created_at,
                    (e.embedding <=> %s::vector) AS distance
                FROM memory_embeddings e
                JOIN messages m ON e.source_message_id = m.message_id
                WHERE e.conversation_id = %s
                ORDER BY e.embedding <=> %s::vector ASC
                LIMIT %s;
                """,
                (query_vector_str, conversation_id, query_vector_str, k)
            )
            rows = cur.fetchall()

            results = []
            for row in rows:
                results.append({
                    "memory_id": str(row[0]),
                    "content": row[1],
                    "caregiver_name": row[2],
                    "note_type": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "distance": float(row[5])
                })
            return results
