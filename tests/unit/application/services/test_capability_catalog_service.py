from __future__ import annotations

import pytest

from src.application.services.capability_catalog_service import (
    CapabilityCatalogService,
    CapabilityValidationError,
)
from src.infrastructure.definitions.yaml_node_definition_source import YamlNodeDefinitionSource


def test_catalog_startup_validation_fails_on_unsupported_executor_type() -> None:
    import shutil
    from pathlib import Path
    from uuid import uuid4

    base = Path("tmp") / f"capability_catalog_test_{uuid4().hex}"
    definitions_dir = base / "definitions" / "nodes"
    schema_path = base / "definitions" / "schemas" / "node_definition_schema.json"
    definitions_dir.mkdir(parents=True, exist_ok=True)
    schema_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        schema_path.write_text(
            '{\n  "type": "object",\n  "required": ["name", "kind", "version", "executor_type"]\n}\n',
            encoding="utf-8",
        )
        (definitions_dir / "bad.yaml").write_text(
            'name: bad\nkind: node\nversion: "1.0.0"\nexecutor_type: does_not_exist\n',
            encoding="utf-8",
        )

        catalog = CapabilityCatalogService(
            sources=[
                YamlNodeDefinitionSource(definitions_dir=definitions_dir, schema_path=schema_path)
            ]
        )

        with pytest.raises(CapabilityValidationError, match="unsupported executor_type"):
            catalog.load_and_validate_startup()
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_catalog_can_load_all_repo_node_definitions() -> None:
    from pathlib import Path

    definitions_dir = Path("definitions/nodes")
    schema_path = Path("definitions/schemas/node_definition_schema.json")

    catalog = CapabilityCatalogService(
        sources=[YamlNodeDefinitionSource(definitions_dir=definitions_dir, schema_path=schema_path)]
    )
    definitions = catalog.load_and_validate_startup()

    assert definitions
    assert len(definitions) == len(list(definitions_dir.glob("*.yaml")))
    assert all(isinstance(d.get("name"), str) and d.get("name") for d in definitions)
    assert all(
        isinstance(d.get("_source_path"), str) and d.get("_source_path") for d in definitions
    )
