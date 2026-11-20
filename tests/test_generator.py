import json
from pathlib import Path

from api_test_agent.generation.generator import generate_test_file
from api_test_agent.generation.model_client import GenerationRequest

PAYLOAD = {
    "base_url": "http://localhost:5000",
    "endpoints": [
        {
            "method": "GET",
            "path": "/health",
            "operation_id": "health_check",
            "has_request_body": False,
            "response_codes": ["200"],
        }
    ],
}


class _FakeModelClient:
    """Modèle factice déterministe pour les tests : pas d'appel réseau."""

    def generate(self, request: GenerationRequest) -> str:
        scenarios = [
            {
                "operation_id": endpoint["operation_id"],
                "scenario": "nominal",
                "method": endpoint["method"],
                "path": endpoint["path"],
                "body": None,
                "expected_status": [200],
            }
            for endpoint in request.contract_payload["endpoints"]
        ]
        return json.dumps(scenarios)


class _AlwaysInvalidModelClient:
    """Simule un modèle qui ne renvoie jamais de JSON exploitable."""

    def generate(self, request: GenerationRequest) -> str:
        return "this is not json at all"


def test_generate_test_file_creates_pytest_file(tmp_path: Path):
    artifact = generate_test_file(
        contract_payload=PAYLOAD,
        output_dir=tmp_path,
        model_client=_FakeModelClient(),
    )

    assert artifact.file_path.exists()
    content = artifact.file_path.read_text(encoding="utf-8")
    assert "def test_health_check_nominal" in content
    # +1 pour le test_unknown_route_returns_client_error de l'en-tête commun.
    assert artifact.test_count == 2
    assert artifact.failed_batch_count == 0
    assert artifact.uncovered_endpoints == []
    # artifact.scenarios doit porter les MÊMES scénarios que ceux rendus dans
    # le fichier .py (utilisé par generation/storage.py pour scenarios.json) —
    # pas une liste vide oubliée par erreur.
    assert [s.operation_id for s in artifact.scenarios] == ["health_check"]
    assert artifact.scenarios[0].scenario == "nominal"


def test_generate_test_file_embeds_auth_headers_and_marks_protected_endpoints(tmp_path: Path):
    payload = {
        "base_url": "http://localhost:5000",
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/articles",
                "operation_id": "createArticle",
                "has_request_body": True,
                "response_codes": ["201"],
                "requires_auth": True,
            }
        ],
    }

    class _ProtectedEndpointModelClient:
        def generate(self, request: GenerationRequest) -> str:
            return json.dumps(
                [
                    {
                        "operation_id": "createArticle",
                        "scenario": "nominal",
                        "method": "POST",
                        "path": "/api/articles",
                        "body": {"title": "x"},
                        "expected_status": [201],
                    }
                ]
            )

    artifact = generate_test_file(
        contract_payload=payload,
        output_dir=tmp_path,
        model_client=_ProtectedEndpointModelClient(),
        auth_headers={"Authorization": "Bearer abc123"},
    )

    content = artifact.file_path.read_text(encoding="utf-8")
    assert "AUTH_HEADERS = {'Authorization': 'Bearer abc123'}" in content
    assert "def test_createarticle_nominal" in content
    assert "auth=True" in content


def test_generate_test_file_includes_deterministic_negative_scenarios_even_if_model_fails(tmp_path: Path):
    payload = {
        "base_url": "http://localhost:5000",
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/categories",
                "operation_id": "createCategory",
                "has_request_body": True,
                "response_codes": ["201", "400", "401"],
                "response_schemas": {},
                "requires_auth": True,
                "request_body_schema": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string"}},
                },
            }
        ],
    }

    artifact = generate_test_file(
        contract_payload=payload,
        output_dir=tmp_path,
        model_client=_AlwaysInvalidModelClient(),
    )

    content = artifact.file_path.read_text(encoding="utf-8")
    assert "def test_createcategory_token_absent" in content
    assert "def test_createcategory_token_invalide" in content
    assert "def test_createcategory_champ_name_manquant" in content
    assert "def test_createcategory_champ_name_type_invalide" in content
    # Le modèle a échoué pour cet endpoint : il reste "non couvert" au sens de
    # la génération LLM, même si des tests négatifs déterministes existent.
    assert artifact.uncovered_endpoints == ["createCategory"]


def test_generate_test_file_marks_batch_failed_when_model_output_invalid(tmp_path: Path):
    artifact = generate_test_file(
        contract_payload=PAYLOAD,
        output_dir=tmp_path,
        model_client=_AlwaysInvalidModelClient(),
    )

    assert artifact.failed_batch_count == 1
    assert artifact.uncovered_endpoints == ["health_check"]
    # Seul le test_unknown_route_returns_client_error de l'en-tête reste.
    assert artifact.test_count == 1
