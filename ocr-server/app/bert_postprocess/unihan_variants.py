"""Cached UniHan variant groups used by candidate-only OCR correction."""

from functools import lru_cache
import gzip
import json
from pathlib import Path
import re


DEFAULT_UNIHAN_DATA_PATH = (
    Path(__file__).resolve().parent / "data" / "unihan_ocr_features.json.gz"
)
VARIANT_FIELDS = (
    "kSemanticVariant",
    "kZVariant",
    "kSpecializedSemanticVariant",
)
_CODEPOINT = re.compile(r"U\+([0-9A-Fa-f]{4,6})")


@lru_cache(maxsize=4)
def _load_index(path: str) -> dict[str, dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        payload = json.load(source)
    records = payload.get("records", {})
    return records if isinstance(records, dict) else {}


@lru_cache(maxsize=4)
def _variant_adjacency(path: str) -> dict[str, set[str]]:
    """Build the undirected graph once per packaged index."""
    records = _load_index(path)
    adjacency: dict[str, set[str]] = {}
    for codepoint, record in records.items():
        source = chr(int(codepoint, 16))
        targets: set[str] = set()
        for field in VARIANT_FIELDS:
            targets.update(
                chr(int(match.group(1), 16))
                for match in _CODEPOINT.finditer(record.get(field, ""))
            )
        if targets:
            adjacency.setdefault(source, set()).update(targets)
            for target in targets:
                adjacency.setdefault(target, set()).add(source)
    return adjacency


@lru_cache(maxsize=65536)
def _get_variant_group(char: str, path: str) -> frozenset[str]:
    if not isinstance(char, str) or len(char) != 1:
        return frozenset()

    # Variant links are treated as an undirected transitive graph. Rare Nom
    # characters without UniHan records are a normal empty lookup.
    adjacency = _variant_adjacency(path)

    if char not in adjacency:
        return frozenset()
    seen = {char}
    pending = [char]
    while pending:
        current = pending.pop()
        for variant in adjacency.get(current, ()):
            if variant not in seen:
                seen.add(variant)
                pending.append(variant)
    return frozenset(seen)


def get_variant_group(
    char: str,
    data_path: str | Path = DEFAULT_UNIHAN_DATA_PATH,
) -> set[str]:
    """Return the semantic/Z/specialized-semantic variant component."""

    return set(_get_variant_group(char, str(Path(data_path).resolve())))


def are_variants(left: str, right: str) -> bool:
    return left != right and right in get_variant_group(left)
