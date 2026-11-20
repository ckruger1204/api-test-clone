from .stage import Stage
from ..discovery.main import DiscoveryStage
from ..analysis.main import AnalysisStage
from ..generation.main import GenerationStage
from ..generation.load_stage import LoadStage
from ..execution.main import ExecutionStage
from ..execution.view_stage import ViewStage
from ..reporting.main import ReportingStage

MODES = ("generate", "load", "view")


def build_stages(mode: str = "generate") -> list[Stage]:
    """Sélectionne les stages du pipeline selon le mode (voir cli/main.py) :

    - "generate" (défaut) : pipeline complet, identique à avant l'introduction
      des modes — spec OpenAPI + modèle requis.
    - "load" : charge une suite déjà sauvegardée dans tests_dir (sans LLM) et
      l'exécute.
    - "view" : charge le contexte de la suite puis affiche un run déjà exécuté,
      sans jamais relancer pytest ("consulter les résultats précédents")."""
    if mode == "generate":
        return [
            DiscoveryStage("discovery"),
            AnalysisStage("analysis"),
            GenerationStage("generation"),
            ExecutionStage("execution"),
            ReportingStage("reporting"),
        ]
    if mode == "load":
        return [
            LoadStage("load"),
            ExecutionStage("execution"),
            ReportingStage("reporting"),
        ]
    if mode == "view":
        return [
            LoadStage("load"),
            ViewStage("view"),
            ReportingStage("reporting"),
        ]
    raise ValueError(f"Mode inconnu : {mode!r} (attendu : {', '.join(MODES)}).")


def default_stages() -> list[Stage]:
    """Conservé pour compatibilité : équivaut à build_stages("generate")."""
    return build_stages("generate")
