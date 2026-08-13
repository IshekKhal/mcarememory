import logging
import psycopg
from app.config import COCKROACH_URL
from app.embeddings import generate_embedding

logger = logging.getLogger(__name__)

def get_connection():
    """Returns a psycopg connection to CockroachDB based on DB_MODE."""
    from app.config import DB_MODE, COCKROACH_URL, COCKROACH_CLOUD_URL
    if DB_MODE in ("cloud", "cloud-mcp") and COCKROACH_CLOUD_URL:
        url = COCKROACH_CLOUD_URL
        if "sslmode=verify-full" in url and "sslrootcert=" not in url:
            url = url.replace("sslmode=verify-full", "sslmode=require")
        return psycopg.connect(url, connect_timeout=10)
    return psycopg.connect(COCKROACH_URL, connect_timeout=10)

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
    k: int = 5,
    query_vector: list[float] | None = None,
    return_metrics: bool = False
) -> list[dict] | tuple[list[dict], dict]:
    """
    Given a question (or precomputed query_vector), retrieves top-k nearest
    embedding matches scoped to conversation_id, and returns matching notes with metadata,
    including any resolution notes in the conversation.
    
    Args:
        conversation_id (str): UUID string of the target conversation.
        question (str): The search query or question text.
        k (int): Number of top matches to retrieve.
        query_vector (list[float], optional): Optional precomputed 1024-dim embedding.
        return_metrics (bool): If True, returns (results, metrics_dict).
        
    Returns:
        list[dict] or (list[dict], dict): List of matching note dicts, and optional metrics dict.
    """
    import time
    if not question and query_vector is None:
        raise ValueError("Search question or query_vector must be provided.")

    t_embed_start = time.perf_counter()
    if query_vector is None:
        query_vector = generate_embedding(question)
    embed_ms = (time.perf_counter() - t_embed_start) * 1000.0

    from app.config import DB_MODE

    query_vector_str = f"[{','.join(str(f) for f in query_vector)}]"

    # MCP select_query has a 16,384 char limit.
    # Full-precision float64 values are ~20 chars each → 1024 dims ≈ 21K chars.
    # Round to 6 decimal places for MCP path: ~9 chars each → ~9K chars (negligible precision loss).
    query_vector_str_mcp = f"[{','.join(f'{f:.6f}' for f in query_vector)}]"

    sql_knn = """
        SELECT 
            e.memory_id,
            e.content,
            m.caregiver_name,
            m.note_type,
            m.created_at,
            e.distance,
            m.message_id,
            m.resolves_note_ids
        FROM (
            SELECT 
                memory_id, 
                source_message_id, 
                conversation_id, 
                content, 
                (embedding <-> %s::vector) AS distance
            FROM memory_embeddings
            ORDER BY embedding <-> %s::vector ASC
            LIMIT 500
        ) e
        JOIN messages m ON e.source_message_id = m.message_id
        WHERE e.conversation_id = %s
        ORDER BY e.distance ASC
        LIMIT %s;
    """

    sql_resolutions = """
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
    """

    if DB_MODE == "cloud-mcp":
        # MCP select_query has a 16,384 char limit.
        # A 1024-dim vector literal is ~10K chars, so we use a CTE to reference it only once.
        sql_knn_mcp = """
            WITH qv AS (SELECT %s::vector AS v)
            SELECT
                e.memory_id, e.content,
                m.caregiver_name, m.note_type, m.created_at,
                e.distance, m.message_id, m.resolves_note_ids
            FROM (
                SELECT memory_id, source_message_id, conversation_id, content,
                       (embedding <-> (SELECT v FROM qv)) AS distance
                FROM memory_embeddings
                ORDER BY embedding <-> (SELECT v FROM qv) ASC
                LIMIT 500
            ) e
            JOIN messages m ON e.source_message_id = m.message_id
            WHERE e.conversation_id = %s
            ORDER BY e.distance ASC
            LIMIT %s;
        """
        from app.mcp_client import CockroachCloudMCPClient
        t_sql_start = time.perf_counter()
        client = CockroachCloudMCPClient()
        raw_rows = client.execute_sql_query(sql_knn_mcp, [query_vector_str_mcp, conversation_id, k])
        res_rows = client.execute_sql_query(sql_resolutions, [conversation_id])
        raw_sql_ms = (time.perf_counter() - t_sql_start) * 1000.0

        results = []
        seen_message_ids = set()
        for r in raw_rows:
            if isinstance(r, dict):
                msg_id = str(r.get("message_id") or r.get("memory_id"))
                seen_message_ids.add(msg_id)
                results.append({
                    "memory_id": str(r.get("memory_id")),
                    "message_id": msg_id,
                    "content": r.get("content", ""),
                    "caregiver_name": r.get("caregiver_name", "Unknown"),
                    "note_type": r.get("note_type", "general"),
                    "created_at": r.get("created_at"),
                    "distance": float(r.get("distance", 0.0)),
                    "resolves_note_ids": r.get("resolves_note_ids") or []
                })
            elif isinstance(r, (list, tuple)):
                msg_id = str(r[6]) if len(r) > 6 and r[6] else str(r[0])
                seen_message_ids.add(msg_id)
                results.append({
                    "memory_id": str(r[0]),
                    "message_id": msg_id,
                    "content": r[1],
                    "caregiver_name": r[2],
                    "note_type": r[3],
                    "created_at": r[4].isoformat() if hasattr(r[4], 'isoformat') else str(r[4]) if r[4] else None,
                    "distance": float(r[5]),
                    "resolves_note_ids": [str(x) for x in r[7]] if len(r) > 7 and r[7] else []
                })

        for r in res_rows:
            if isinstance(r, dict):
                msg_id = str(r.get("message_id"))
                if msg_id not in seen_message_ids:
                    seen_message_ids.add(msg_id)
                    results.append({
                        "memory_id": str(r.get("memory_id")),
                        "message_id": msg_id,
                        "content": r.get("content", ""),
                        "caregiver_name": r.get("caregiver_name", "Unknown"),
                        "note_type": r.get("note_type", "resolution"),
                        "created_at": r.get("created_at"),
                        "distance": 0.0,
                        "resolves_note_ids": r.get("resolves_note_ids") or []
                    })
            elif isinstance(r, (list, tuple)):
                msg_id = str(r[5]) if len(r) > 5 else str(r[0])
                if msg_id not in seen_message_ids:
                    seen_message_ids.add(msg_id)
                    results.append({
                        "memory_id": str(r[0]),
                        "message_id": msg_id,
                        "content": r[1],
                        "caregiver_name": r[2],
                        "note_type": r[3],
                        "created_at": r[4].isoformat() if hasattr(r[4], 'isoformat') else str(r[4]) if r[4] else None,
                        "distance": 0.0,
                        "resolves_note_ids": [str(x) for x in r[6]] if len(r) > 6 and r[6] else []
                    })

        results = deduplicate_retrieved_notes(results)
        metrics = {
            "embed_latency_ms": embed_ms,
            "raw_sql_latency_ms": raw_sql_ms,
            "total_recall_ms": embed_ms + raw_sql_ms
        }
        if return_metrics:
            return results, metrics
        return results

    with get_connection() as conn:
        with conn.cursor() as cur:
            t_sql_start = time.perf_counter()
            cur.execute(sql_knn, (query_vector_str, query_vector_str, conversation_id, k))
            rows = cur.fetchall()
            raw_sql_ms = (time.perf_counter() - t_sql_start) * 1000.0

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

            cur.execute(sql_resolutions, (conversation_id,))
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
                    
            results = deduplicate_retrieved_notes(results)
            metrics = {
                "embed_latency_ms": embed_ms,
                "raw_sql_latency_ms": raw_sql_ms,
                "total_recall_ms": embed_ms + raw_sql_ms
            }

            if return_metrics:
                return results, metrics
            return results

def deduplicate_retrieved_notes(notes: list[dict]) -> list[dict]:
    """
    Permanent retrieval-layer safeguard:
    Drops any note sharing identical (caregiver_name, content) with one
    already in the result set, keeping only the earliest matching note.
    """
    deduped = []
    seen_keys = set()
    for note in notes:
        cname = (note.get("caregiver_name") or "").strip()
        content = (note.get("content") or "").strip()
        key = (cname, content)
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(note)
    return deduped


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


# Alias for backward compatibility and benchmarking
search_similar_notes = recall_relevant_notes



