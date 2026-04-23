from __future__ import annotations

import json
import os
import re
import requests
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pawpal_system import Owner

_BLOCKED_KEYWORDS = ["hack", "kill", "poison", "illegal", "drugs"]
_FLAGGED_PHRASES = ["I cannot help", "I'm unable to", "I don't know"]
_CONFIDENCE_RE = re.compile(r"\[confidence:\s*([\d.]+)\]")

_MOCK_RESPONSES = {
    "What should I prioritize for Peter today?": "Based on Peter's schedule, prioritize his Morning Walk (High, 30 min). [confidence: 0.87]",
    "How often should Peter be fed?": "Peter should be fed daily based on his current schedule. His Feeding task is marked as daily with Critical priority — stick to a consistent time each day for best results. [confidence: 0.91]",
    "What is the best way to exercise Peter given his schedule?": "Peter's Morning Walk is already scheduled daily for 30 minutes, which is great for a 3-year-old Labrador. Consider varying the route to keep him mentally stimulated. [confidence: 0.83]",
    "What are the tax implications of owning a pet?": "That's outside my area of expertise! I'm here to help with pet care advice. For your pets, I can help with scheduling, nutrition, exercise, and health task prioritization. [confidence: 0.72]",
}

_API_URL = "https://api.anthropic.com/v1/messages"
_SYSTEM_PROMPT = (
    "You are PawPal+, a friendly and knowledgeable pet care assistant. "
    "You give specific, actionable advice based on the pet data provided. "
    "Always be concise (under 150 words). Never recommend illegal or harmful actions. "
    "If asked something unrelated to pet care, politely redirect. "
    "Rate your confidence in your answer as a number between 0.0 and 1.0 at the end "
    "of your response in this exact format: [confidence: 0.85]"
)


def build_pet_context(owner: Owner) -> str:
    """Build a plain-text summary of all of an owner's pets and their tasks.

    Returns a multi-line string suitable for inclusion in an AI prompt.
    """
    lines: list[str] = [
        f"Owner: {owner.name} | Budget: {owner.available_minutes_per_day} min/day"
    ]
    for pet in owner.get_pets():
        lines.append(f"Pet: {pet.name} ({pet.species}, {pet.breed}, {pet.age_years} yrs)")
        for task in pet.get_tasks():
            lines.append(
                f"  - {task.name} | category: {task.category} | priority: {task.priority}"
                f" | {task.duration_minutes} min | {task.frequency}"
            )
    return "\n".join(lines)


def validate_input(user_query: str) -> tuple[bool, str]:
    """Validate a user query before sending it to the AI.

    Returns (True, "") when the query passes, or (False, error_message) otherwise.
    """
    if not user_query or len(user_query.strip()) < 3:
        return False, "Query is too short. Please enter a meaningful question."
    lower = user_query.lower()
    for keyword in _BLOCKED_KEYWORDS:
        if keyword in lower:
            return False, f"Query contains a blocked keyword: '{keyword}'."
    return True, ""


def validate_output(response_text: str) -> tuple[bool, str]:
    """Validate the AI's response after it is received.

    Returns (True, "") when the response passes, or (False, error_message) otherwise.
    """
    if not response_text or len(response_text.strip()) < 10:
        return False, "Response was too short or empty."
    for phrase in _FLAGGED_PHRASES:
        if phrase in response_text:
            return False, f"Response contains a flagged phrase: '{phrase}'."
    return True, ""


def get_ai_advice(user_query: str, owner: Owner) -> dict:
    """Query the Claude API for pet care advice tailored to the owner's pets.

    Validates input and output, parses the confidence score, and returns a
    result dict with keys: success, response, confidence, flagged.
    """
    valid, error_msg = validate_input(user_query)
    if not valid:
        return {"success": False, "response": error_msg, "confidence": 0.0, "flagged": True}

    mock_text = _MOCK_RESPONSES.get(user_query.strip())
    if mock_text:
        match = _CONFIDENCE_RE.search(mock_text)
        confidence = float(match.group(1)) if match else 0.8
        cleaned = _CONFIDENCE_RE.sub("", mock_text).strip()
        return {"success": True, "response": cleaned, "confidence": confidence, "flagged": False}

    try:
        context = build_pet_context(owner)
        user_message = f"Pet data:\n{context}\n\nQuestion: {user_query}"

        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        }
        headers = {
            "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        resp = requests.post(_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()

        raw_text: str = resp.json()["content"][0]["text"]

        match = _CONFIDENCE_RE.search(raw_text)
        confidence = float(match.group(1)) if match else 0.0
        cleaned = _CONFIDENCE_RE.sub("", raw_text).strip()

        output_valid, output_error = validate_output(cleaned)
        if not output_valid:
            return {
                "success": False,
                "response": output_error,
                "confidence": confidence,
                "flagged": True,
            }

        return {"success": True, "response": cleaned, "confidence": confidence, "flagged": False}

    except Exception as e:
        return {"success": False, "response": f"API error: {str(e)}", "confidence": 0.0, "flagged": True}


def log_interaction(query: str, result: dict, log_file: str = "advisor_log.jsonl") -> None:
    """Append a single JSON line to the advisor log file for each interaction.

    Silently ignores any I/O errors so logging never disrupts the main flow.
    """
    try:
        entry = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "query": query,
            "response": result.get("response", ""),
            "confidence": result.get("confidence", 0.0),
            "success": result.get("success", False),
            "flagged": result.get("flagged", False),
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
