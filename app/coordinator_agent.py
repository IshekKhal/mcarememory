from datetime import datetime
import logging
import anthropic
from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from app.memory_store import recall_relevant_notes

logger = logging.getLogger(__name__)

def format_human_timestamp(ts) -> str:
    """
    Formats a database timestamp string or object into a human-readable format
    (e.g. '2:00 PM' or 'Tuesday 2:00 PM') so raw ISO strings are never passed to the LLM.
    """
    if not ts:
        return "N/A"
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif isinstance(ts, datetime):
            dt = ts
        else:
            return str(ts)
            
        time_part = dt.strftime("%I:%M %p").lstrip("0")
        day_part = dt.strftime("%A")
        return f"{day_part} {time_part}"
    except Exception:
        return str(ts)

SYSTEM_PROMPT = """You are an AI coordinator assistant helping family members and caregivers coordinate care for an aging relative by synthesizing recorded caregiver notes.

GUIDELINES:
1. Synthesize a direct, coherent, natural-language response based strictly on the provided caregiver notes. Speak like a clear, warm, direct person communicating with a family member — not a corporate report or a robotic customer service bot.
2. Do NOT just list or excerpt the notes line-by-line or bullet-by-bullet unless specifically requested. Synthesize them into a clear narrative summary.
3. HUMAN-READABLE TIMESTAMPS:
   - Always refer to times in human-friendly terms (e.g., "2:00 PM" or "Tuesday 2:00 PM"). Never output raw ISO timestamp strings (like "2026-08-06T14:00:00Z").
4. WRITING TONE & PHRASING RULES:
   - NO REFLEXIVE EM DASHES: Avoid using em dashes ("—") as default connectors. Use commas, periods, or split sentences naturally.
   - NO REPETITIVE TICS OR FORMULAIC CLOSINGS: Never use canned phrases like "worth a quick check", "worth noting", "worth flagging", "quick heads-up", or identical closing sentences across answers. State discrepancies directly and vary your phrasing naturally between questions.
   - SPECIFIC NAMED ATTRIBUTION: Always name specific caregivers directly (e.g., "Maria, David, and Alex all noted...") instead of vague collective phrases like "multiple caregivers' notes indicate" or "confirmed across multiple notes".
   - VARIED LENGTH & STRUCTURE: Match answer length to the question. Short, simple questions without conflicts get brief, direct answers. Do not pad answers with unnecessary fluff or repetitive hedges.
   - PLAIN DIRECT LANGUAGE: Use plain, conversational words instead of softened corporate phrasing or robotic AI filler.
5. CONFLICT DETECTION & SURFACING:
   - Carefully analyze the retrieved notes for factual conflicts or discrepancies between caregivers regarding the same subject or event (e.g. medication reported as given vs. missed, contradictory mood/behavior observations, or conflicting appointment details).
   - UNRESOLVED CONFLICTS: If a factual conflict exists between notes and has NOT been resolved by a resolution note, surface the exact mismatch directly and calmly. State clearly who reported what (naming caregivers, times, and exact contradictory facts). Keep all factual details accurate while sounding like a direct person pointing out a mismatch.
   - RESOLVED CONFLICTS: If a resolution note exists in the context that clarifies or resolves a previous mismatch (or references the conflicting note IDs), state the confirmed final outcome plainly and mention that it was resolved (e.g., "The 2:00 PM blood pressure medication was given, as confirmed with Maria after an initial mix-up with Nurse Sarah's note.").
   - NO CONFLICT: If no conflict exists, provide a simple, unified answer without inventing issues.
6. ZERO HALLUCINATION & FACTUAL FREQUENCY ACCURACY:
   - If the provided notes do not contain relevant information to answer the question, state clearly and directly that you do not have that information in the notes. Do NOT guess, assume, or hallucinate facts.
   - Preserve exact counts, frequencies, and note attributions. If a caregiver logged an action once, state it occurred once (do not embellish with "a couple of times" or "frequently"). If a single note contains conflicting internal details (e.g. morning dose logged at 9:00 PM), describe it accurately as a single entry without splitting it into multiple separate entries.
7. MEDICAL ADVICE GUARDRAIL: You are an assistant summarizing caregiver notes, NOT a medical professional giving clinical advice. If the question asks for medical judgment or clinical decisions (e.g., changing medication dosage, diagnosing symptoms, altering treatment plans), surface what the notes factually state about past occurrences, but explicitly state that a doctor or qualified healthcare professional must be consulted for medical decisions.
"""


def answer_caregiver_question(
    conversation_id: str,
    question: str,
    k: int = 5
) -> str:
    """
    Retrieves top-k relevant caregiver notes for the question, formats them as context,
    and calls the Anthropic Claude API (claude-haiku-4-5-20251001) to synthesize a direct,
    natural-language answer with conflict-awareness.

    Args:
        conversation_id (str): Target conversation UUID.
        question (str): Caregiver query.
        k (int): Number of relevant notes to recall (default: 5).

    Returns:
        str: Synthesized answer or error message.
    """
    if not question or not question.strip():
        return "[Error] Question cannot be empty."

    if not ANTHROPIC_API_KEY or not ANTHROPIC_API_KEY.strip():
        error_msg = (
            "[Error] ANTHROPIC_API_KEY environment variable is not set. "
            "Please add ANTHROPIC_API_KEY=your_key to your environment or .env file."
        )
        logger.error(error_msg)
        return error_msg

    # 1. Recall relevant notes from vector store
    try:
        notes = recall_relevant_notes(conversation_id=conversation_id, question=question, k=k)
    except Exception as e:
        error_msg = f"[Error] Failed to recall memory notes: {e}"
        logger.exception(error_msg)
        return error_msg

    # 2. Handle 0 relevant notes case
    if not notes:
        return "I don't have any relevant caregiver notes or information about that in my memory store."

    # 3. Format retrieved notes for context
    formatted_notes_list = []
    for idx, note in enumerate(notes, start=1):
        caregiver = note.get("caregiver_name", "Unknown Caregiver")
        note_type = note.get("note_type", "general")
        content = note.get("content", "")
        msg_id = note.get("message_id", "")
        resolves = note.get("resolves_note_ids", [])
        
        note_header = f"Note #{idx} [ID: {msg_id}]"
        if note_type == "resolution":
            note_header += f" (RESOLUTION NOTE - Resolves Note IDs: {resolves})"
            
        formatted_notes_list.append(
            f"{note_header}:\n"
            f"  Caregiver: {caregiver}\n"
            f"  Category: {note_type}\n"
            f"  Content: \"{content}\""
            + (f"\n  Resolves Note IDs: {resolves}" if resolves else "")
        )
    formatted_notes = "\n\n".join(formatted_notes_list)

    user_prompt = f"""Question from caregiver: "{question}"

Retrieved Caregiver Notes:
{formatted_notes}

Based strictly on the notes above, synthesize a clear, direct, and natural-language answer to the caregiver's question. 
Remember:
- Use human-readable timestamps (e.g. 2:00 PM or Tuesday 2:00 PM), never raw ISO strings.
- State facts and any unresolved caregiver mismatches directly, naming specific caregivers (e.g. Maria, Nurse Sarah).
- Keep the phrasing natural, warm, and direct. Do not use em dashes ("—"), repetitive canned phrases ("worth a quick check"), or vague collective phrases ("multiple caregivers' notes").
- Match answer length to the question: keep simple answers concise."""


    # 4. Call Anthropic Messages API
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        if response and response.content:
            return response.content[0].text.strip()
        else:
            return "[Error] Received empty response from Anthropic API."

    except anthropic.AuthenticationError:
        error_msg = "[Error] Anthropic API authentication failed. Please check if ANTHROPIC_API_KEY is valid."
        logger.error(error_msg)
        return error_msg
    except anthropic.RateLimitError:
        error_msg = "[Error] Anthropic API rate limit exceeded. Please wait a moment and try again."
        logger.error(error_msg)
        return error_msg
    except anthropic.APIConnectionError as e:
        error_msg = f"[Error] Network connection failed while reaching Anthropic API: {e}"
        logger.error(error_msg)
        return error_msg
    except anthropic.APIError as e:
        error_msg = f"[Error] Anthropic API error ({e.status_code}): {e.message}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"[Error] Unexpected error during LLM synthesis: {e}"
        logger.exception(error_msg)
        return error_msg

