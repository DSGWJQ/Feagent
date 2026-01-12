"""Capability catalog service (Application).

Loads node capability definitions via CapabilityDefinitionSource and performs
startup validation (fail-fast).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.ports.capability_definition_source import (
    CapabilityDefinition,
    CapabilityDefinitionSource,
)


@dataclass(frozen=True, slots=True)
class CapabilityValidationError(ValueError):
    message: str
    source_path: str | None = None

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        prefix = f"{self.source_path}: " if self.source_path else ""
        return f"{prefix}{self.message}"


class CapabilityCatalogService:
    # Executor types currently used by `definitions/nodes/*.yaml`.
    # Treat this as the single source of truth for startup validation.
    SUPPORTED_NODE_EXECUTOR_TYPES: set[str] = {
        "api",
        "code",
        "database",
        "file",
        "generic",
        "human",
        "llm",
        "notification",
        "parallel",
        "python",
        "sequential",
        "transform",
        "workflow",
    }

    def __init__(self, *, sources: Iterable[CapabilityDefinitionSource]) -> None:
        self._sources = list(sources)

    def load_all(self) -> list[CapabilityDefinition]:
        definitions: list[CapabilityDefinition] = []
        for source in self._sources:
            definitions.extend(source.load())
        return definitions

    def validate_startup(self, definitions: list[CapabilityDefinition]) -> None:
        seen_names: set[str] = set()

        for definition in definitions:
            if not isinstance(definition, dict):
                raise CapabilityValidationError("definition must be a mapping")

            source_path = _get_source_path(definition)
            name = definition.get("name")
            if not isinstance(name, str) or not name.strip():
                raise CapabilityValidationError("missing/invalid name", source_path=source_path)

            if name in seen_names:
                raise CapabilityValidationError(f"duplicate name: {name}", source_path=source_path)
            seen_names.add(name)

            executor_type = definition.get("executor_type")
            if not isinstance(executor_type, str) or not executor_type.strip():
                raise CapabilityValidationError(
                    "missing/invalid executor_type", source_path=source_path
                )

            if executor_type not in self.SUPPORTED_NODE_EXECUTOR_TYPES:
                supported = ", ".join(sorted(self.SUPPORTED_NODE_EXECUTOR_TYPES))
                raise CapabilityValidationError(
                    f"unsupported executor_type: {executor_type} (supported: {supported})",
                    source_path=source_path,
                )

    def load_and_validate_startup(self) -> list[CapabilityDefinition]:
        definitions = self.load_all()
        self.validate_startup(definitions)
        return definitions


def _get_source_path(definition: dict[str, Any]) -> str | None:
    raw = definition.get("_source_path")
    if isinstance(raw, str) and raw:
        try:
            return str(Path(raw))
        except Exception:  # pragma: no cover
            return raw
    return None
