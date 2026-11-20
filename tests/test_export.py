import json
from pathlib import Path

from api_test_agent.reporting.export import export_html, export_json

SAMPLE_REPORT = {
    "mode": "generate",
    "summary": {"passed": 1, "failed": 0, "error": 0, "skipped": 0, "not_executed": 0, "total": 1},
    "tests": [{"name": "test_x", "outcome": "passed"}],
}


def test_export_json_round_trips(tmp_path: Path):
    path = export_json(SAMPLE_REPORT, tmp_path / "report.json")

    assert json.loads(path.read_text(encoding="utf-8")) == SAMPLE_REPORT


def test_export_json_creates_parent_directories(tmp_path: Path):
    path = export_json(SAMPLE_REPORT, tmp_path / "nested" / "run" / "report.json")

    assert path.exists()


def test_export_html_embeds_report_before_existing_script(tmp_path: Path):
    template = tmp_path / "index.html"
    template.write_text("<html><body>viewer</body><script>console.log('hi')</script></html>", encoding="utf-8")

    output = export_html(SAMPLE_REPORT, template, tmp_path / "report.html")
    html = output.read_text(encoding="utf-8")

    assert "window.__EMBEDDED_REPORT__" in html
    assert '"name": "test_x"' in html
    # Le script embarqué doit précéder le script original du template.
    assert html.index("__EMBEDDED_REPORT__") < html.index("console.log")


def test_export_html_escapes_closing_script_tag_in_response_bodies(tmp_path: Path):
    template = tmp_path / "index.html"
    template.write_text("<html><body></body><script></script></html>", encoding="utf-8")

    report = {
        "mode": "generate",
        "summary": {},
        "tests": [{"name": "t", "requests": [{"response_body": "<script>alert(1)</script>"}]}],
    }

    output = export_html(report, template, tmp_path / "report.html")
    html = output.read_text(encoding="utf-8")

    # La chaîne piégée ne doit jamais fermer prématurément la balise <script>
    # qui porte les données embarquées : sa propre balise fermante est échappée.
    assert "alert(1)<\\/script>" in html
    assert "<script>alert(1)</script>" not in html


def test_export_html_appends_script_when_template_has_none(tmp_path: Path):
    template = tmp_path / "index.html"
    template.write_text("<html><body>no script here</body></html>", encoding="utf-8")

    output = export_html(SAMPLE_REPORT, template, tmp_path / "report.html")
    html = output.read_text(encoding="utf-8")

    assert "window.__EMBEDDED_REPORT__" in html
