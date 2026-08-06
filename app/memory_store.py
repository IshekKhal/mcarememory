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
            cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS resolves_note_ids TEXT[];")
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

def add_resolution_note(
    conversation_id: str,
    caregiver_name: str,
    content: str,
    resolves_note_ids: list[str] | None = None
) -> str:
    """
    Records a resolution note that clarifies or resolves previously recorded conflicting caregiver notes.
    
    Args:
        conversation_id (str): UUID string of the active conversation.
        caregiver_name (str): Name or role of the person logging the resolution.
        content (str): Text explaining the resolved outcome.
        resolves_note_ids (list[str]): List of message_id UUID strings of conflicting notes resolved.
        
    Returns:
        str: Created message_id (UUID string).
    """
    if not content or not content.strip():
        raise ValueError("Resolution note content cannot be empty.")
    if not caregiver_name or not caregiver_name.strip():
        raise ValueError("Caregiver name cannot be empty.")
        
    resolves_list = [str(nid) for nid in (resolves_note_ids or [])]

    # Generate real embedding via SageMaker BGE-large-en-v1.5
    embedding_vector = generate_embedding(content)
    embedding_str = f"[{','.join(str(f) for f in embedding_vector)}]"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS resolves_note_ids TEXT[];")
            
            cur.execute(
                """
                INSERT INTO messages (conversation_id, role, content, caregiver_name, note_type, resolves_note_ids)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING message_id;
                """,
                (conversation_id, "user", content, caregiver_name, "resolution", resolves_list)
            )
            message_row = cur.fetchone()
            message_id = str(message_row[0])

            cur.execute(
                """
                INSERT INTO memory_embeddings (conversation_id, source_message_id, content, embedding)
                VALUES (%s, %s, %s, %s::vector);
                """,
                (conversation_id, message_id, content, embedding_str)
            )

            conn.commit()
            logger.info(f"Added resolution note [{message_id}] by '{caregiver_name}' resolving notes {resolves_list}")
            return message_id

def recall_relevant_notes(
    conversation_id: str,
    question: str,
    k: int = 5
) -> list[dict]:
    """
    Given a question, generates its embedding, queries CockroachDB for top-k nearest
    embedding matches scoped to conversation_id, and returns matching notes with metadata,
    including any resolution notes in the conversation.
    
    Args:
        conversation_id (str): UUID string of the target conversation.
        question (str): The search query or question text.
        k (int): Number of top matches to retrieve.
        
    Returns:
        list[dict]: List of matching note dicts containing memory_id, message_id, content,
                    caregiver_name, note_type, created_at, resolves_note_ids, and distance score.
    """
    if not question or not question.strip():
        raise ValueError("Search question cannot be empty.")

    # Generate query embedding
    query_vector = generate_embedding(question)
    query_vector_str = f"[{','.join(str(f) for f in query_vector)}]"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS resolves_note_ids TEXT[];")
            
            cur.execute(
                """
                SELECT 
                    e.memory_id,
                    e.content,
                    m.caregiver_name,
                    m.note_type,
                    m.created_at,
                    (e.embedding <=> %s::vector) AS distance,
                    m.message_id,
                    m.resolves_note_ids
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
            seen_message_ids = set()
            for row in rows:
                msg_id = str(row[6]) if row[6] else str(row[0])
                seen_message_ids.add(msg_id)
                results.append({
                    "memory_id": str(row[0]),
                    "message_id": msg_id,
                    "content": row[1],
                    "caregiver_name": row[2],
                    "note_type": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "distance": float(row[5]),
                    "resolves_note_ids": [str(x) for x in row[7]] if row[7] else []
                })

            # Also fetch any resolution notes for this conversation to ensure full resolution context
            cur.execute(
                """
                SELECT 
                    e.memory_id,
                    e.content,
                    m.caregiver_name,
                    m.note_type,
                    m.created_at,
                    m.message_id,
                    m.resolves_note_ids
                FROM memory_embeddings e
                JOIN messages m ON e.source_message_id = m.message_id
                WHERE e.conversation_id = %s AND m.note_type = 'resolution';
                """,
                (conversation_id,)
            )
            res_rows = cur.fetchall()
            for row in res_rows:
                msg_id = str(row[5])
                if msg_id not in seen_message_ids:
                    seen_message_ids.add(msg_id)
                    results.append({
                        "memory_id": str(row[0]),
                        "message_id": msg_id,
                        "content": row[1],
                        "caregiver_name": row[2],
                        "note_type": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "distance": 0.0,
                        "resolves_note_ids": [str(x) for x in row[6]] if row[6] else []
                    })
                    
            return results

def get_caregiver_notes(conversation_id: str) -> list[dict]:
    """
    Retrieves all recorded caregiver notes for the specified conversation,
    ordered by created_at DESC (most recent first).
    
    Args:
        conversation_id (str): Target conversation UUID.
        
    Returns:
        list[dict]: List of note dictionaries.
    """
    if not conversation_id:
        return []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS resolves_note_ids TEXT[];")
            cur.execute(
                """
                SELECT 
                    message_id,
                    caregiver_name,
                    note_type,
                    content,
                    created_at,
                    resolves_note_ids
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at DESC;
                """,
                (conversation_id,)
            )
            rows = cur.fetchall()
            notes = []
            for row in rows:
                notes.append({
                    "message_id": str(row[0]),
                    "caregiver_name": row[1] or "Unknown Caregiver",
                    "note_type": row[2] or "general",
                    "content": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "resolves_note_ids": [str(x) for x in row[5]] if row[5] else []
                })
            return notes


