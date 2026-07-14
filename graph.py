"""
LangGraph Workflow Definition

Defines the StateGraph that orchestrates the Tea Shop Agent workflow.
Nodes are connected with conditional edges for branching logic:

    START → receive_message → detect_intent
      → (intent routing)
          ADD_SALES/ADD_EXPENSES:
              → (has_image?) → ocr → groq_extract / groq_extract
              → (needs_retry?) → groq_extract (retry)
              → validate
              → (is_valid?) → write_sheets → save_confirmation → reply / reply (errors)
          REPORT:
              → generate_report → reply
          HELP:
              → reply
      → END
"""

import logging
from langgraph.graph import StateGraph, START, END
from state import AgentState

# Import all node functions
from nodes.receive_message import receive_message
from nodes.detect_intent import detect_intent
from nodes.ocr import ocr_process
from nodes.groq_extract import groq_extract
from nodes.validate import validate
from nodes.sheets import write_sheets
from nodes.reports import generate_report, generate_save_confirmation
from nodes.reply import reply

logger = logging.getLogger(__name__)


# ── Routing functions for conditional edges ───────────────────────────

def route_by_intent(state: AgentState) -> str:
    """Route based on detected intent."""
    intent = state.get("intent", "HELP")
    logger.info(f"Routing by intent: {intent}")

    if intent in ("ADD_SALES", "ADD_EXPENSES"):
        return "add_data"
    elif intent == "REPORT":
        return "report"
    else:
        return "help"


def route_by_image(state: AgentState) -> str:
    """Route based on whether the message has an image."""
    if state.get("has_image", False):
        logger.info("Message has image → OCR path")
        return "has_image"
    else:
        logger.info("Text only → direct extraction")
        return "text_only"


def route_by_retry(state: AgentState) -> str:
    """Route based on whether extraction needs a retry."""
    parsed = state.get("parsed_json", {})
    retry_count = state.get("retry_count", 0)
    has_error = state.get("is_valid") is False and state.get("error", "")

    # If we got empty parsed_json and retry_count just incremented, retry
    if not parsed and retry_count > 0 and retry_count <= 1 and not has_error:
        logger.info(f"Retrying extraction (attempt {retry_count + 1})")
        return "retry"
    else:
        return "continue"


def route_by_validation(state: AgentState) -> str:
    """Route based on validation result."""
    if state.get("is_valid", False):
        logger.info("Validation passed → write to sheets")
        return "valid"
    else:
        logger.info("Validation failed → reply with errors")
        return "invalid"


# ── Build the graph ───────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph StateGraph for the Tea Shop Agent.

    Returns:
        Compiled graph ready for .invoke()
    """
    builder = StateGraph(AgentState)

    # ── Register all nodes ────────────────────────────────────────────
    builder.add_node("receive_message", receive_message)
    builder.add_node("detect_intent", detect_intent)
    builder.add_node("ocr", ocr_process)
    builder.add_node("groq_extract", groq_extract)
    builder.add_node("validate", validate)
    builder.add_node("write_sheets", write_sheets)
    builder.add_node("save_confirmation", generate_save_confirmation)
    builder.add_node("generate_report", generate_report)
    builder.add_node("reply", reply)

    # ── Entry edge ────────────────────────────────────────────────────
    builder.add_edge(START, "receive_message")
    builder.add_edge("receive_message", "detect_intent")

    # ── Intent routing ────────────────────────────────────────────────
    builder.add_conditional_edges(
        "detect_intent",
        route_by_intent,
        {
            "add_data": "ocr",        # Check for image first (OCR handles no-image too)
            "report": "generate_report",
            "help": "reply",
        },
    )

    # ── Image routing (OCR → extract or skip OCR) ────────────────────
    # OCR node handles both cases: if no image, it passes text through
    builder.add_edge("ocr", "groq_extract")

    # ── Retry routing ─────────────────────────────────────────────────
    builder.add_conditional_edges(
        "groq_extract",
        route_by_retry,
        {
            "retry": "groq_extract",  # Loop back for retry
            "continue": "validate",
        },
    )

    # ── Validation routing ────────────────────────────────────────────
    builder.add_conditional_edges(
        "validate",
        route_by_validation,
        {
            "valid": "write_sheets",
            "invalid": "reply",
        },
    )

    # ── Post-save flow ────────────────────────────────────────────────
    builder.add_edge("write_sheets", "save_confirmation")
    builder.add_edge("save_confirmation", "reply")

    # ── Report flow ───────────────────────────────────────────────────
    builder.add_edge("generate_report", "reply")

    # ── Terminal edge ─────────────────────────────────────────────────
    builder.add_edge("reply", END)

    # ── Compile ───────────────────────────────────────────────────────
    graph = builder.compile()
    logger.info("LangGraph workflow compiled successfully")

    return graph


# Compile the graph at module level for reuse
workflow = build_graph()
