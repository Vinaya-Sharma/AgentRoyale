from __future__ import annotations


def answer(question: str, task: dict) -> dict:
    """Tiny demo target for the static smoke task pack."""
    task_id = task.get("id", "")
    if task_id == "smoke_price":
        return {
            "answer": "$19.00",
            "citations": [{"url": "https://example.com/pricing", "quote": "Pro plan $19.00"}],
            "trace": {"tools_used": ["example.static"], "cost_usd": 0},
        }
    if task_id == "smoke_followers":
        return {
            "answer": "12,500",
            "citations": [{"url": "https://example.com/social", "quote": "Followers 12,500"}],
            "trace": {"tools_used": ["example.static"], "cost_usd": 0},
        }
    return {"answer": "I do not know.", "citations": []}
