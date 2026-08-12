import os
import sys
import logging
from flask import Flask, jsonify, request, send_from_directory

# Ensure project root is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.memory_store import (
    create_conversation,
    add_caregiver_note,
    get_caregiver_notes
)
from app.coordinator_agent import (
    answer_caregiver_question,
    format_human_timestamp
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("web_server")

# Path to active conversation ID file
ID_FILEPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "active_conversation.id"))
STATIC_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))

app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path="")


def get_active_conversation_id() -> str:
    """Loads saved conversation ID from centralized config (app.config.ACTIVE_CONVERSATION_ID)."""
    from app.config import ACTIVE_CONVERSATION_ID
    return ACTIVE_CONVERSATION_ID



@app.route("/")
def index():
    """Serves the main static single-page interface."""
    return send_from_directory(STATIC_FOLDER, "index.html")


@app.route("/api/notes", methods=["GET"])
def list_notes():
    """Returns the current list of caregiver notes for the active conversation, most recent first."""
    try:
        cid = get_active_conversation_id()
        raw_notes = get_caregiver_notes(cid)

        notes = []
        for n in raw_notes:
            notes.append({
                "message_id": n["message_id"],
                "caregiver_name": n["caregiver_name"],
                "note_type": n["note_type"],
                "content": n["content"],
                "created_at": n["created_at"],
                "human_timestamp": format_human_timestamp(n["created_at"]),
                "resolves_note_ids": n.get("resolves_note_ids", [])
            })

        return jsonify({
            "status": "success",
            "conversation_id": cid,
            "count": len(notes),
            "notes": notes
        }), 200
    except Exception as e:
        logger.exception("Error listing notes")
        return jsonify({
            "status": "error",
            "message": f"Failed to retrieve notes: {str(e)}"
        }), 500


@app.route("/api/notes", methods=["POST"])
def create_note():
    """Accepts a new caregiver note and persists it with vector embeddings."""
    try:
        data = request.get_json(silent=True) or {}
        caregiver_name = data.get("caregiver_name", "").strip()
        note_type = data.get("note_type", "general").strip()
        content = data.get("content", "").strip()

        if not caregiver_name:
            return jsonify({"status": "error", "message": "Caregiver name is required."}), 400
        if not content:
            return jsonify({"status": "error", "message": "Note content cannot be empty."}), 400

        cid = get_active_conversation_id()
        message_id = add_caregiver_note(
            conversation_id=cid,
            caregiver_name=caregiver_name,
            content=content,
            note_type=note_type
        )

        return jsonify({
            "status": "success",
            "message_id": message_id,
            "conversation_id": cid
        }), 201

    except ValueError as ve:
        return jsonify({"status": "error", "message": str(ve)}), 400
    except Exception as e:
        logger.exception("Error writing caregiver note")
        err_msg = str(e)
        if "SageMaker" in err_msg or "endpoint" in err_msg or "ClientError" in err_msg:
            user_msg = "Failed to write note: SageMaker embedding endpoint is offline or unavailable."
        else:
            user_msg = f"Failed to write caregiver note: {err_msg}"
        return jsonify({"status": "error", "message": user_msg}), 500


@app.route("/api/ask", methods=["POST"])
def ask_question():
    """Accepts a caregiver question and synthesizes a conflict-aware answer using Claude Haiku 4.5."""
    try:
        data = request.get_json(silent=True) or {}
        question = data.get("question", "").strip()
        k = data.get("k", 5)

        if not question:
            return jsonify({"status": "error", "message": "Question text cannot be empty."}), 400

        cid = get_active_conversation_id()
        answer = answer_caregiver_question(conversation_id=cid, question=question, k=k)

        return jsonify({
            "status": "success",
            "conversation_id": cid,
            "question": question,
            "answer": answer
        }), 200

    except Exception as e:
        logger.exception("Error answering question")
        return jsonify({
            "status": "error",
            "message": f"Failed to synthesize answer: {str(e)}"
        }), 500


if __name__ == "__main__":
    cid = get_active_conversation_id()
    print("=" * 70)
    print("Milestone 9 Web Server: Grandma Chen's Care Coordinator UI")
    print(f"Active Conversation ID: {cid}")
    print("Serving at: http://localhost:5000")
    print("=" * 70)
    app.run(host="0.0.0.0", port=5000, debug=True)
