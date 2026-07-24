from __future__ import annotations

from ..normalization import normalize_title


def token_set(text: str) -> set[str]:
    normalized = normalize_title(text)
    return {token for token in normalized.replace("-", " ").split() if token}


def jaccard_similarity(left: str, right: str) -> float:
    left_set = token_set(left)
    right_set = token_set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def near_duplicate_pairs(records: list[dict], *, threshold: float = 0.82) -> list[tuple[int, int, float]]:
    pairs: list[tuple[int, int, float]] = []
    for i, left in enumerate(records):
        for j in range(i + 1, len(records)):
            right = records[j]
            score = jaccard_similarity(left.get("normalized_title") or left.get("title") or "", right.get("normalized_title") or right.get("title") or "")
            if score >= threshold:
                pairs.append((i, j, score))
    return pairs
