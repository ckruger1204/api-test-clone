from __future__ import annotations

import json
from typing import Any


def build_generation_prompt(contract_payload: dict[str, Any]) -> str:
    normalized_payload = json.dumps(
        contract_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return (
        "You are an API test generator. Generate ONLY valid Python test code for pytest. "
        "Use urllib from the Python standard library (no external deps), one happy-path test per endpoint, "
        "and include one generic error test for an unknown route. "
        "Do not use markdown fences. "
        "Contract payload JSON: "
        f"{normalized_payload}"
    )
