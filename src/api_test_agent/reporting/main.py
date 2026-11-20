
from ..pipeline.stage import Stage
from ..pipeline.context import RunContext
from ..exit_codes import ExitCode
from .export import export_html, export_json
from .report_builder import build_detailed_report
from loguru import logger

class ReportingStage(Stage):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: RunContext) -> None:
        logger.info("reporting stage started")

        generation_failed = False
        if ctx.generation_stats:
            endpoints_total = ctx.generation_stats.get("endpoints_total", 0)
            endpoints_covered = ctx.generation_stats.get("endpoints_covered", 0)
            uncovered_endpoints = ctx.generation_stats.get("uncovered_endpoints", [])
            batch_count = ctx.generation_stats.get("batch_count", 0)
            failed_batch_count = ctx.generation_stats.get("failed_batch_count", 0)
            tests_generated = ctx.generation_stats.get("test_count", len(ctx.generated_tests))
            generation_failed = failed_batch_count > 0 or bool(uncovered_endpoints)
        else:
            endpoints_total = len((ctx.model_payload or {}).get("endpoints", []))
            endpoints_covered = endpoints_total
            uncovered_endpoints = []
            batch_count = 0
            failed_batch_count = 0
            tests_generated = len(ctx.generated_tests)

        # ctx.results est rempli par ExecutionStage/ViewStage avec des dicts
        # ayant la même forme que TestResult (name, outcome, duration_s,
        # message, endpoint, requests, assertions) : outcome vaut "passed",
        # "failed", "error" ou "skipped".
        passed = sum(1 for result in ctx.results if result.get("outcome") == "passed")
        failed = sum(1 for result in ctx.results if result.get("outcome") in ("failed", "error"))
        skipped = sum(1 for result in ctx.results if result.get("outcome") == "skipped")

        # Rapport détaillé : joint ctx.results avec ctx.scenarios (description,
        # statut attendu) et calcule les scénarios "not_executed" — voir
        # reporting/report_builder.py. Exporté en JSON et en HTML autonome
        # (données inlinées) dans le run courant/consulté, et mirroré vers
        # reports/results.json pour le viewer live (inchangé, voir README).
        report = build_detailed_report(ctx)
        ctx.report = report
        not_executed = report["summary"].get("not_executed", 0)

        live_dir = ctx.workdir / "reports"
        live_dir.mkdir(parents=True, exist_ok=True)
        export_json(report, live_dir / "results.json")

        if ctx.run_dir:
            export_json(report, ctx.run_dir / "report.json")
            template_path = live_dir / "index.html"
            if template_path.is_file():
                export_html(report, template_path, ctx.run_dir / "report.html")

        summary = {
            "endpoints_total": endpoints_total,
            "endpoints_covered": endpoints_covered,
            "tests_generated": tests_generated,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "not_executed": not_executed,
        }
        ctx.summary = summary

        lines = [
            "API Test Agent run summary",
            f"- Mode: {ctx.mode}",
            f"- Endpoints: {endpoints_covered}/{endpoints_total} covered",
            f"- Batches: {batch_count} (échoués: {failed_batch_count})",
            f"- Tests generated: {tests_generated}",
            f"- Passed: {passed}",
            f"- Failed: {failed}",
            f"- Skipped: {skipped}",
            f"- Not executed: {not_executed}",
        ]
        if uncovered_endpoints:
            lines.append(f"- Endpoints non couverts: {', '.join(uncovered_endpoints)}")
        if ctx.generation_stats and ctx.generation_stats.get("raw_responses_path"):
            lines.append(f"- Réponses brutes de Qwen: {ctx.generation_stats['raw_responses_path']}")
        if ctx.run_dir:
            lines.append(f"- Rapport détaillé : {ctx.run_dir / 'report.json'}")
            lines.append(f"- Export HTML autonome : {ctx.run_dir / 'report.html'}")

        execution_failed = False
        if ctx.execution_stats:
            outcome = ctx.execution_stats.get("outcome")
            lines.append(f"- Execution outcome: {outcome}")
            if ctx.execution_stats.get("message"):
                lines.append(f"- {ctx.execution_stats['message']}")
            if ctx.execution_stats.get("results_json_path"):
                lines.append(f"- Résultats détaillés: {ctx.execution_stats['results_json_path']}")
            if ctx.execution_stats.get("log_path"):
                lines.append(f"- Logs bruts: {ctx.execution_stats['log_path']}")
            execution_failed = outcome != "success"

        logger.info("\n".join(lines))

        if failed > 0 or execution_failed:
            ctx.exit_code = ExitCode.TEST_FAILURES
        elif generation_failed:
            ctx.exit_code = ExitCode.GENERATION_ERROR

        logger.success("reporting stage completed ✅")
