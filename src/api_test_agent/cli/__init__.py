# Attention : cet import rebind l'attribut `api_test_agent.cli.main` (le
# sous-module) vers cette fonction, puisqu'ils portent le même nom. Un
# `import api_test_agent.cli.main as x` ailleurs récupère alors la fonction,
# pas le module ; utiliser `importlib.import_module("api_test_agent.cli.main")`
# si on a besoin du module (voir tests/test_cli_main.py).
from .main import main

__all__ = ["main"]