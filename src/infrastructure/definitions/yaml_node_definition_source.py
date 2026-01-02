"""YAML-backed CapabilityDefinitionSource for node capabilities.

Loads YAML files from `definitions/nodes` (repo root) and validates required fields
from the JSON schema in `definitions/schemas/node_definition_schema.json`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.domain.ports.capability_definition_source import (
    CapabilityDefinition,
    CapabilityDefinitionSource,
)


class NodeDefinitionLoadError(ValueError):
    def __init__(self, source_path: Path, message: str) -> None:
        super().__init__(f"{source_path}: {message}")
        self.source_path = source_path
        self.message = message


class YamlNodeDefinitionSource(CapabilityDefinitionSource):
    def __init__(
        self,
        *,
        definitions_dir: Path,
        schema_path: Path,
    ) -> None:
        self._definitions_dir = definitions_dir
        self._schema_path = schema_path

    def load(self) -> list[CapabilityDefinition]:
        if not self._definitions_dir.exists():
            raise NodeDefinitionLoadError(self._definitions_dir, "definitions_dir does not exist")

        required_keys = self._load_required_keys()
        definitions: list[CapabilityDefinition] = []

        for yaml_path in sorted(self._definitions_dir.glob("*.yaml")):
            definitions.append(self._load_one(yaml_path, required_keys=required_keys))

        return definitions

    def _load_required_keys(self) -> set[str]:
        if not self._schema_path.exists():
            raise NodeDefinitionLoadError(self._schema_path, "schema_path does not exist")

        try:
            import json

            schema = json.loads(self._schema_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - explicit startup failure
            raise NodeDefinitionLoadError(self._schema_path, f"invalid schema json: {exc}") from exc

        required = schema.get("required", [])
        if not isinstance(required, list) or not all(isinstance(k, str) for k in required):
            raise NodeDefinitionLoadError(
                self._schema_path, "schema.required must be a string list"
            )

        return set(required)

    def _load_one(self, yaml_path: Path, *, required_keys: set[str]) -> CapabilityDefinition:
        try:
            raw_text = yaml_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise NodeDefinitionLoadError(yaml_path, f"read failed: {exc}") from exc

        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            line_info = ""
            mark = getattr(exc, "problem_mark", None)
            if mark is not None:
                line_info = f":{mark.line + 1}:{mark.column + 1}"
            raise NodeDefinitionLoadError(yaml_path, f"yaml parse error{line_info}: {exc}") from exc

        if not isinstance(data, dict):
            raise NodeDefinitionLoadError(yaml_path, "top-level YAML must be a mapping")

        missing = [k for k in sorted(required_keys) if k not in data]
        if missing:
            raise NodeDefinitionLoadError(yaml_path, f"missing required keys: {', '.join(missing)}")

        # Keep a traceable pointer for startup validation / error reporting.
        # This key is intentionally namespaced to avoid colliding with domain fields.
        data = dict(data)
        data["_source_path"] = str(yaml_path)

        return data  # type: ignore[return-value]
