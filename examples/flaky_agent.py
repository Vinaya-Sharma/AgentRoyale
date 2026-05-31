from __future__ import annotations


def answer(question: str, task: dict) -> dict:
    """Demo target that intentionally gets one smoke task wrong."""
    task_id = task.get("id", "")
    if task_id == "smoke_price":
        return {
            "answer": "$29.00",
            "citations": [
                {
                    "url": "https://example.com/pricing",
                    "quote": "Business plan $29.00 per month",
                }
            ],
            "trace": {"tools_used": ["example.cached_search"], "cost_usd": 0},
        }
    if task_id == "smoke_followers":
        return {
            "answer": "12,500",
            "citations": [
                {
                    "url": "https://example.com/social",
                    "quote": "Followers 12,500",
                }
            ],
            "trace": {"tools_used": ["example.static"], "cost_usd": 0},
        }
    return {"answer": "I could not find the value.", "citations": []}
