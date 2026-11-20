from api_test_agent.generation.payloads import (
    build_example_from_schema,
    build_invalid_example_from_schema,
)

ARTICLE_INPUT_SCHEMA = {
    "type": "object",
    "required": ["title", "content"],
    "properties": {
        "title": {"type": "string", "minLength": 3, "maxLength": 200},
        "content": {"type": "string", "minLength": 1},
        "summary": {"type": "string", "nullable": True},
        "published": {"type": "boolean", "default": True},
        "category_id": {"type": "integer", "nullable": True},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}


def test_build_example_from_schema_fills_only_required_fields():
    example = build_example_from_schema(ARTICLE_INPUT_SCHEMA)

    assert set(example.keys()) == {"title", "content"}
    assert isinstance(example["title"], str) and len(example["title"]) >= 3
    assert isinstance(example["content"], str)


def test_build_example_from_schema_uses_explicit_example():
    schema = {"type": "string", "example": "flask"}
    assert build_example_from_schema(schema) == "flask"


def test_build_example_from_schema_uses_default_when_no_example():
    schema = {"type": "boolean", "default": False}
    assert build_example_from_schema(schema) is False


def test_build_example_from_schema_respects_min_length():
    schema = {"type": "string", "minLength": 20}
    example = build_example_from_schema(schema)
    assert len(example) >= 20


def test_build_example_from_schema_respects_enum():
    schema = {"type": "string", "enum": ["recent", "oldest", "title"]}
    assert build_example_from_schema(schema) == "recent"


def test_build_example_from_schema_merges_all_of():
    schema = {
        "allOf": [
            {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}},
            {"type": "object", "required": ["email"], "properties": {"email": {"type": "string", "format": "email"}}},
        ]
    }
    example = build_example_from_schema(schema)
    assert set(example.keys()) == {"id", "email"}
    assert "@" in example["email"]


def test_build_example_from_schema_array_of_objects():
    schema = {
        "type": "array",
        "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
    }
    example = build_example_from_schema(schema)
    assert example == [{"name": "texte_test"}]


def test_build_invalid_example_removes_first_required_field():
    invalid = build_invalid_example_from_schema(ARTICLE_INPUT_SCHEMA)

    assert "title" not in invalid
    assert "content" in invalid


def test_build_invalid_example_corrupts_type_when_no_required_field():
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}

    invalid = build_invalid_example_from_schema(schema)

    assert invalid["name"] == {"__type_invalide_pour_ce_champ__": True}


def test_build_invalid_example_returns_none_for_non_object_schema():
    assert build_invalid_example_from_schema({"type": "string"}) is None
    assert build_invalid_example_from_schema(None) is None
