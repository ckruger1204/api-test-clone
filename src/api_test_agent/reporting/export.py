from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_json(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def export_html(report: dict[str, Any], template_path: Path, output_path: Path) -> Path:
    """Produit un rapport HTML autonome (données inlinées, ouvrable sans
    serveur) à partir du template reports/index.html — le viewer live lui-même
    n'est pas modifié : il garde son fetch('./results.json') par défaut, et
    n'utilise les données embarquées ci-dessous que si elles sont présentes
    (voir le script loadResults() du template)."""
    template = template_path.read_text(encoding="utf-8")
    embedded = json.dumps(report, ensure_ascii=False)
    # Un body de réponse capturé peut légitimement contenir la sous-chaîne
    # "</script" (ex: une page d'erreur HTML de l'API testée) : il faut
    # l'échapper pour ne pas fermer prématurément la balise <script> ci-dessous.
    embedded = embedded.replace("</script", "<\\/script")
    snippet = f"<script>window.__EMBEDDED_REPORT__ = {embedded};</script>\n"

    if "<script>" in template:
        html = template.replace("<script>", snippet + "<script>", 1)
    else:
        html = template + snippet

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
