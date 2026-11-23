from __future__ import annotations

from ..models import SignalEvidence
from .base import Context

TARGET_MIN_DOWNLOADS = 100_000
KEYBOARD_ROWS = [
    "`1234567890-=",
    "qwertyuiop[]\\",
    "asdfghjkl;'",
    "zxcvbnm,./",
]
KEYBOARD_POSITIONS = {
    char: (row, col)
    for row, chars in enumerate(KEYBOARD_ROWS)
    for col, char in enumerate(chars)
}

HOMOGLYPHS = str.maketrans({
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t",
    "@": "a", "$": "s", "!": "i", "|": "l",
})


def keyboard_adjacent(left: str, right: str) -> bool:
    a = KEYBOARD_POSITIONS.get(left)
    b = KEYBOARD_POSITIONS.get(right)
    if a is None or b is None:
        return False
    return abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1


def keyboard_typo(left: str, right: str) -> bool:
    if len(left) != len(right) or left == right:
        return False
    mismatches = [
        (a, b) for a, b in zip(left, right) if a != b
    ]
    return bool(mismatches) and all(keyboard_adjacent(a, b) for a, b in mismatches)


_LENGTH_INDEX_CACHE: dict[int, tuple[list[str], dict[int, list[str]]]] = {}


def _length_index(top_names: list[str]) -> dict[int, list[str]]:
    key = id(top_names)
    cached = _LENGTH_INDEX_CACHE.get(key)
    if cached is not None and cached[0] is top_names:
        return cached[1]
    index: dict[int, list[str]] = {}
    for candidate in top_names:
        index.setdefault(len(candidate), []).append(candidate)
    if len(_LENGTH_INDEX_CACHE) > 32:
        _LENGTH_INDEX_CACHE.clear()
    _LENGTH_INDEX_CACHE[key] = (top_names, index)
    return index


def normalize_homoglyphs(name: str) -> str:
    if name.startswith("@") and "/" in name:
        scope, package = name.split("/", 1)
        return scope + "/" + package.translate(HOMOGLYPHS)
    return name.translate(HOMOGLYPHS)


def levenshtein(a: str, b: str, max_distance: int | None = None) -> int:
    """Damerau-Levenshtein (OSA), capped at max_distance + 1 when requested."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    if max_distance is not None and abs(la - lb) > max_distance:
        return max_distance + 1
    limit = max_distance if max_distance is not None else max(la, lb)
    rows = [list(range(lb + 1))]
    for i in range(1, la + 1):
        previous = rows[-1]
        current = [i] + [0] * lb
        row_min = current[0]
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            value = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + cost,
            )
            if (
                i > 1
                and j > 1
                and a[i - 1] == b[j - 2]
                and a[i - 2] == b[j - 1]
            ):
                value = min(value, rows[i - 2][j - 2] + cost)
            current[j] = value
            if value < row_min:
                row_min = value
        if row_min > limit:
            return limit + 1
        rows.append(current)
    distance = rows[-1][lb]
    if max_distance is not None:
        return min(distance, max_distance + 1)
    return distance


def compute(ctx: Context) -> SignalEvidence:
    if not ctx.top_names:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no top package list available"},
        )

    name = ctx.name.lower()
    normalized_name = normalize_homoglyphs(name)
    best: tuple[int, str | None, bool, bool] = (3, None, False, False)
    index = _length_index(ctx.top_names)
    for length in range(len(name) - 2, len(name) + 3):
        for candidate in index.get(length, []):
            other = candidate.lower()
            if other == name:
                continue
            normalized_other = normalize_homoglyphs(other)
            distance = levenshtein(name, other, 2)
            if distance > 1 and normalized_other != other:
                distance = min(
                    distance,
                    levenshtein(normalized_name, normalized_other, 2),
                )
            homoglyph = normalized_name == normalized_other and name != other
            keyboard = keyboard_typo(name, other) if len(name) == len(other) else False
            if distance < best[0]:
                best = (distance, other, homoglyph, keyboard)
                if distance == 1:
                    break
        if best[0] == 1:
            break

    distance, nearest, homoglyph, keyboard = best
    suspicious = (
        homoglyph
        or keyboard
        or distance == 1
        or (distance == 2 and len(name) > 8)
    )
    if suspicious and ctx.downloads_weekly < 1000:
        value = 1.0
    elif suspicious:
        value = 0.2
    else:
        value = 0.0

    return SignalEvidence(
        value=value,
        evidence={
            "distance": distance,
            "nearest": nearest,
            "homoglyph": homoglyph,
            "keyboard_typo": keyboard,
            "downloads_weekly": ctx.downloads_weekly,
        },
    )
