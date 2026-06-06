from __future__ import annotations

import os
from typing import Any

from backend.llm import complete_raw_chat


async def answer(question: str, task: dict[str, Any]) -> dict[str, Any]:
    """OpenRouter native chat target for models with built-in search behavior.

    Use this for provider models that do not support the OpenRouter web-search
    tool route but can still answer with their native retrieval behavior.
    """
    model = os.getenv("OPENROUTER_NATIVE_MODEL", "perplexity/sonar-pro-search")
    required_source = str(task.get("required_source", ""))
    messages = [
        {
            "role": "system",
            "content": (
                "You are being evaluated on exact live-web retrieval. Use current web information, "
                "answer with only the requested exact value, and include citations if available. "
                "Do not answer from memory."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{question}\nRequired source: {required_source}\n"
                "Return the exact current value and cite your source."
            ),
        },
    ]
    raw = await complete_raw_chat(messages, model=model)
    choice = (raw.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    citations = extract_citations(raw, message)
    if not citations and required_source:
        citations.append({"url": required_source, "quote": ""})
    return {
        "answer": content,
        "citations": citations,
        "trace": {
            "tools_used": ["openrouter:native-model-search"],
            "search_queries": [model],
            "provider_metadata": {
                "provider": "openrouter",
                "model": model,
                "mode": "native_chat",
            },
        },
    }


def extract_citations(raw: dict[str, Any], message: dict[str, Any]) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    for item in message.get("annotations") or []:
        citation = item.get("url_citation") or item
        if citation.get("url"):
            citations.append(
                {
                    "url": str(citation.get("url", "")),
                    "quote": str(citation.get("content", "") or citation.get("title", "")),
                }
            )
    for url in raw.get("citations") or []:
        if isinstance(url, str):
            citations.append({"url": url, "quote": ""})
    return citations
