from api_test_agent.analysis.prompt import build_generation_prompt


def test_prompt_is_deterministic():
    payload = {
        "title": "Demo",
        "version": "1.0",
        "base_url": "http://localhost:5000",
        "endpoints": [
            {"method": "GET", "path": "/health", "response_codes": ["200"], "has_request_body": False}
        ],
    }

    prompt1 = build_generation_prompt(payload)
    prompt2 = build_generation_prompt(payload)

    assert prompt1 == prompt2
    assert "Contract payload JSON" in prompt1
