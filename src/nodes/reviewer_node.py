# reviewer_node.py
from pydantic import BaseModel, Field
from typing import List
from services.review import review_error_logs, generate_rewrite_plan
from logger import log_review


def reviewer_node(state):
    """
    Reviewer node: Reviews the error logs and provides analysis and suggestions
    for fixing the errors. This node only focuses on analysis, not file modification.
    """
    print("<reviewer>")
    if len(state["error_logs"]) == 0:
        print("No error to review.")
        print("</reviewer>")
        return state

    # Log error logs to review.log
    log_review(str(state["error_logs"]), "error_logs")

    # Stateless review via service
    history_text = state.get("history_text") or []
    review_content, updated_history = review_error_logs(
        tutorial_reference=state.get('tutorial_reference', ''),
        foamfiles=state.get('foamfiles'),
        error_logs=state.get('error_logs'),
        user_requirement=state.get('user_requirement', ''),
        similar_case_advice=state.get('similar_case_advice'),
        history_text=history_text,
    )

    log_review(review_content, "review_analysis")

    rewrite_plan = generate_rewrite_plan(
        foamfiles=state.get('foamfiles'),
        error_logs=state.get('error_logs', []),
        review_analysis=review_content,
        user_requirement=state.get('user_requirement', ''),
    )
    log_review(str(rewrite_plan), "rewrite_plan")

    print("</reviewer>")

    return {
        "history_text": updated_history,
        "review_analysis": review_content,
        "rewrite_plan": rewrite_plan,
        "loop_count": state.get("loop_count", 0) + 1,
        "input_writer_mode": "rewrite",
    }
