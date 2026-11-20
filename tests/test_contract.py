from api_test_agent.analysis.contract import extract_contract_payload

SPEC_WITH_MIXED_SECURITY = {
    "openapi": "3.0.3",
    "info": {"title": "Demo", "version": "1.0"},
    "security": [{"bearerAuth": []}],
    "paths": {
        "/public": {
            "get": {
                "operationId": "getPublic",
                "security": [],
                "responses": {"200": {}},
            }
        },
        "/optional": {
            "get": {
                "operationId": "getOptional",
                "security": [{}, {"bearerAuth": []}],
                "responses": {"200": {}},
            }
        },
        "/protected": {
            "get": {
                "operationId": "getProtected",
                "security": [{"bearerAuth": []}],
                "responses": {"200": {}, "401": {}},
            }
        },
        "/inherits-global": {
            "get": {
                "operationId": "getInheritsGlobal",
                "responses": {"200": {}, "401": {}},
            }
        },
    },
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
        }
    },
}


def test_extract_contract_payload_extracts_security_schemes():
    payload = extract_contract_payload(SPEC_WITH_MIXED_SECURITY, base_url="http://localhost:5000")

    assert payload["security_schemes"] == {
        "bearerAuth": {"type": "http", "scheme": "bearer", "in": None, "name": None}
    }


def test_extract_contract_payload_requires_auth_per_endpoint():
    payload = extract_contract_payload(SPEC_WITH_MIXED_SECURITY, base_url="http://localhost:5000")

    requires_auth = {e["operation_id"]: e["requires_auth"] for e in payload["endpoints"]}

    assert requires_auth == {
        "getPublic": False,  # security: [] explicite -> aucune auth requise
        "getOptional": False,  # alternative vide {} présente -> auth optionnelle
        "getProtected": True,  # une seule alternative, non vide -> auth requise
        "getInheritsGlobal": True,  # pas de `security` propre -> hérite du global non vide
    }


SPEC_WITH_REQUEST_BODY = {
    "info": {"title": "Demo", "version": "1.0"},
    "paths": {
        "/categories": {
            "post": {
                "operationId": "createCategory",
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/CategoryInput"}}
                    }
                },
                "responses": {"201": {}},
            }
        },
        "/no-body": {
            "get": {"operationId": "listThings", "responses": {"200": {}}},
        },
    },
    "components": {
        "schemas": {
            "CategoryInput": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "minLength": 2},
                    "description": {"type": "string", "nullable": True},
                },
            }
        }
    },
}


def test_extract_contract_payload_resolves_request_body_schema_ref():
    payload = extract_contract_payload(SPEC_WITH_REQUEST_BODY, base_url="http://localhost:5000")

    endpoints = {e["operation_id"]: e for e in payload["endpoints"]}
    assert endpoints["createCategory"]["request_body_schema"] == {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string", "minLength": 2},
            "description": {"type": "string", "nullable": True},
        },
    }
    assert endpoints["listThings"]["request_body_schema"] is None


def test_extract_contract_payload_handles_circular_ref_without_recursion_error():
    spec = {
        "info": {"title": "Demo", "version": "1.0"},
        "paths": {
            "/nodes": {
                "post": {
                    "operationId": "createNode",
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Node"}}
                        }
                    },
                    "responses": {"201": {}},
                }
            }
        },
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {"child": {"$ref": "#/components/schemas/Node"}},
                }
            }
        },
    }

    payload = extract_contract_payload(spec, base_url="http://localhost:5000")

    schema = payload["endpoints"][0]["request_body_schema"]
    assert schema["properties"]["child"] == {}


SPEC_WITH_RESPONSE_SCHEMAS = {
    "info": {"title": "Demo", "version": "1.0"},
    "paths": {
        "/categories/{id}": {
            "get": {
                "operationId": "getCategory",
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Category"}}
                        },
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "204": {"description": "no content, pas de schema"},
                },
            }
        }
    },
    "components": {
        "schemas": {
            "Category": {"type": "object", "properties": {"id": {"type": "integer"}}},
            "Error": {"type": "object", "properties": {"message": {"type": "string"}}},
        },
        "responses": {
            "NotFound": {
                "description": "not found",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
            }
        },
    },
}


def test_extract_contract_payload_resolves_response_schema_directly():
    payload = extract_contract_payload(SPEC_WITH_RESPONSE_SCHEMAS, base_url="http://localhost:5000")

    schemas = payload["endpoints"][0]["response_schemas"]
    assert schemas["200"] == {"type": "object", "properties": {"id": {"type": "integer"}}}


def test_extract_contract_payload_resolves_response_ref_to_components_responses():
    payload = extract_contract_payload(SPEC_WITH_RESPONSE_SCHEMAS, base_url="http://localhost:5000")

    schemas = payload["endpoints"][0]["response_schemas"]
    assert schemas["404"] == {"type": "object", "properties": {"message": {"type": "string"}}}


def test_extract_contract_payload_skips_responses_without_json_content():
    payload = extract_contract_payload(SPEC_WITH_RESPONSE_SCHEMAS, base_url="http://localhost:5000")

    schemas = payload["endpoints"][0]["response_schemas"]
    assert "204" not in schemas


def test_extract_contract_payload_no_security_defaults_to_false():
    spec = {
        "info": {"title": "Demo", "version": "1.0"},
        "paths": {
            "/items": {
                "get": {"operationId": "listItems", "responses": {"200": {}}},
            }
        },
    }

    payload = extract_contract_payload(spec, base_url="http://localhost:5000")

    assert payload["endpoints"][0]["requires_auth"] is False
    assert payload["security_schemes"] == {}
