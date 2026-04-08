from __future__ import annotations

import tiktoken

_ENCODER = tiktoken.get_encoding("cl100k_base")


def truncate_to_token_budget(text: str, budget: int) -> tuple[str, bool]:
    tokens = _ENCODER.encode(text)
    if len(tokens) <= budget:
        return text, False
    truncated = _ENCODER.decode(tokens[:budget])
    return truncated, True


def aggregate_pages(
    pages: list[str],
    per_page_char_limit: int,
    max_pages: int,
    token_budget: int = 80_000,
) -> tuple[str, int, bool]:
    """Combine crawled page markdowns into a single string for the AI.

    Returns (combined_text, pages_included, was_truncated).
    """
    selected = pages[:max_pages]
    parts = [f"--- Page {i + 1} ---\n{page[:per_page_char_limit]}" for i, page in enumerate(selected)]
    combined = "\n\n".join(parts)
    final, was_truncated = truncate_to_token_budget(combined, token_budget)
    return final, len(selected), was_truncated
