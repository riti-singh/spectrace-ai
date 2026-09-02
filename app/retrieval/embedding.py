"""Dependency-free, deterministic domain-semantic feature hashing."""

import hashlib
import math
import re
from collections.abc import Iterable, Mapping
from enum import Enum
from itertools import pairwise
from typing import Any

EMBEDDING_DIMENSIONS = 256
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

_CONCEPTS = {
    "authentication": {"authenticate", "authentication", "credential", "credentials", "identity"},
    "firmware": {"boot", "firmware", "image", "rollback", "software", "update"},
    "handoff": {"handoff", "mobility", "roaming", "transition"},
    "link": {"acquisition", "antenna", "bearer", "beam", "radio", "rf", "satellite"},
    "power": {"consumption", "energy", "power", "rail", "watts"},
    "recovery": {"fail-safe", "failure", "reacquisition", "recovery", "restore"},
    "security": {"authorized", "encryption", "secure", "security", "signature", "tampered"},
    "telemetry": {"health", "management", "monitoring", "report", "telemetry"},
    "thermal": {"cooling", "heat", "temperature", "thermal", "throttling"},
    "traffic": {"congestion", "emergency", "priority", "qos", "scheduler", "traffic"},
    "verification": {"test", "validate", "verification", "verify"},
}
_CANONICAL = {alias: concept for concept, aliases in _CONCEPTS.items() for alias in aliases}


class DeterministicSemanticEncoder:
    """Encode text into stable vectors using concepts, tokens, and character features.

    This deliberately small local encoder is reproducible across machines and avoids remote
    inference, secrets, and model downloads. It is suitable for the bounded synthetic corpus;
    deployments with broader language should replace it behind this narrow interface.
    """

    dimensions = EMBEDDING_DIMENSIONS

    def encode(self, text: str) -> list[float]:
        tokens = [_CANONICAL.get(token, token) for token in _TOKEN_PATTERN.findall(text.lower())]
        features: list[tuple[str, float]] = []
        for token in tokens:
            features.append((f"token:{token}", 2.0))
            padded = f"^{token}$"
            for size in (3, 4):
                features.extend(
                    (f"char:{padded[index : index + size]}", 0.35)
                    for index in range(max(0, len(padded) - size + 1))
                )
        features.extend((f"pair:{left}:{right}", 1.0) for left, right in pairwise(tokens))
        return self._hash_features(features)

    def _hash_features(self, features: Iterable[tuple[str, float]]) -> list[float]:
        vector = [0.0] * self.dimensions
        for feature, weight in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


def entity_search_document(entity: Any) -> str:
    """Build the indexed document from public scalar fields only."""

    raw: Mapping[str, Any]
    if hasattr(entity, "model_dump"):
        raw = entity.model_dump(mode="json")
    elif isinstance(entity, Mapping):
        raw = entity
    else:
        raise TypeError("search documents require a model or mapping")
    values: list[str] = []
    for key, value in raw.items():
        if key.endswith("_ids") or isinstance(value, (list, dict)) or value is None:
            continue
        if isinstance(value, Enum):
            value = value.value
        values.append(str(value))
    return " ".join(values)
