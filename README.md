# api-test-agent

Agent local de génération et d'exécution de tests d'API, piloté par un LLM local (Ollama) à partir d'une spécification OpenAPI. Tu lui donnes une spécification OpenAPI et l'URL d'une API en marche. Il génère des scénarios de test (cas normaux, erreurs attendues, authentification, validation du corps des requêtes) et les exécute avec Pytest. Il produit ensuite un rapport détaillé (HTML autonome et JSON), sans jamais exposer les secrets qu'il utilise.

## Architecture

Le pipeline est une suite d'étapes exécutées l'une après l'autre. Elles partagent un contexte commun, et une erreur arrête le pipeline.

| Étape | Rôle |
|---|---|
| Discovery | Charge et valide le document OpenAPI (YAML ou JSON). |
| Analysis | Extrait le contrat de l'API (endpoints, schémas, sécurité requise) pour le modèle. |
| Generation | Demande au modèle les scénarios par lots, ajoute des scénarios négatifs fixes, écrit le fichier Pytest et sauvegarde les scénarios. |
| Execution | Exécute Pytest, lit les résultats et journalise chaque requête et chaque réponse. |
| Reporting | Joint scénarios et résultats, produit le résumé et les rapports JSON et HTML. |

Deux modes utilisent moins d'étapes : `load` (relit une suite déjà sauvegardée, sans appeler le modèle) et `view` (affiche un run déjà exécuté).

## Installation

Prérequis : Python 3.11 ou plus, et Ollama avec un modèle compatible (par exemple `qwen2.5-coder:1.5b`). Ollama n'est pas nécessaire pour les modes `load` et `view`.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Cette commande installe aussi la commande `api-test-agent`.

## Démarrage rapide (API de démonstration)

Le dépôt contient une petite API Flask de démonstration (JWT, articles et commentaires) avec sa spécification OpenAPI. Ses dépendances sont incluses dans celles du projet.

Terminal 1 : démarrer l'API de démo (`http://127.0.0.1:5000`).

```bash
cd examples/demo_flask_api
python run.py
```

Terminal 2 : à la racine du projet, copier `config.example.json` en `config.json` (en adaptant `model_options` à ton installation Ollama), puis lancer l'agent.

```bash
api-test-agent
```

L'agent génère les scénarios, les exécute contre l'API de démo et affiche un résumé. Les résultats détaillés sont dans `generated_tests/runs/<horodatage>/`.

## Configuration (`config.json`)

Toute la configuration passe par ce fichier. L'agent n'accepte aucun argument en ligne de commande.

| Clé | Défaut | Description |
|---|---|---|
| `mode` | `generate` | `generate`, `load` ou `view` |
| `openapi_spec_path` | – | Chemin du document OpenAPI (requis en mode `generate`) |
| `api_url` | – | URL de base de l'API testée |
| `model_options.base_url` | – | URL du serveur du modèle (Ollama : `http://localhost:11434`) |
| `model_options.model` | `qwen2.5-coder` | Modèle utilisé |
| `model_options.batch_size` | `4` | Nombre d'endpoints envoyés au modèle par appel |
| `model_options.timeout` | `600` | Délai maximal d'un appel au modèle, en secondes |
| `model_options.run_timeout` | `300` | Délai maximal de l'exécution Pytest, en secondes |
| `auth` | – | Authentification de l'API testée |
| `tests_dir` | `generated_tests` | Dossier où la suite est sauvegardée |
| `run_id` | le plus récent | Run affiché en mode `view` |

## Modes d'exécution

- `generate` (défaut) : pipeline complet. Appelle le modèle, exécute les tests et produit le rapport.
- `load` : relit la suite sauvegardée et l'exécute sans appeler le modèle. On peut modifier `scenarios.json` à la main, puis relancer.
- `view` : affiche un run déjà exécuté, sans relancer Pytest.

```json
{ "mode": "load" }
```
```json
{ "mode": "view", "run_id": "20260115-142301" }
```

## Authentification de l'API testée

Si l'API a besoin d'authentification, déclarer une section `auth` dans `config.json`. L'agent lit les schémas de sécurité de la spécification pour savoir quels endpoints sont protégés. Il ajoute les en-têtes seulement sur ceux-là. Trois types sont possibles :

```json
"auth": { "type": "bearer", "token": "${API_TEST_AGENT_TOKEN}" }
```
```json
"auth": { "type": "api_key", "header": "X-Api-Key", "value": "${API_TEST_AGENT_KEY}" }
```
```json
"auth": { "type": "basic", "username": "alice", "password": "${API_TEST_AGENT_PASSWORD}" }
```

Une valeur de la forme `${NOM_VAR}` est lue depuis une variable d'environnement. Le secret n'est jamais écrit dans `scenarios.json` et il est masqué dans les journaux et les rapports.

## Ce que les tests vérifient

Pour chaque endpoint, l'agent combine deux sources de scénarios :

- Ceux du modèle : cas normal, identifiant introuvable, corps mal formé, et cas métier pour les codes de réponse documentés (par exemple 409 ou 403).
- Ceux du code, indépendants du modèle : jeton absent, jeton invalide, un scénario par champ requis manquant et un par champ de type incorrect.

Chaque test vérifie le code HTTP reçu. Quand la spécification documente un schéma de réponse, il vérifie aussi le contenu (champs requis, types, valeurs permises). Il liste toutes les violations trouvées, pas seulement la première.

## Fichiers produits

```text
generated_tests/
├── scenarios.json           # scénarios (modifiable, sans secret)
├── test_generated_api.py    # régénéré depuis scenarios.json, ne pas modifier
├── qwen_raw_responses.json  # réponses brutes du modèle (diagnostic)
└── runs/<horodatage>/       # un dossier par exécution
    ├── results.json, results.xml, pytest_output.log, request_log.jsonl
    ├── report.json          # rapport détaillé
    └── report.html          # rapport autonome, ouvrable sans serveur
```

## Visualiser les résultats

Ouvrir directement `generated_tests/runs/<horodatage>/report.html` dans un navigateur. Le rapport affiche le résumé (réussis, échoués, ignorés, non exécutés) et, pour chaque test, l'objectif, la requête, le statut attendu et obtenu, la réponse reçue et les vérifications effectuées. Les secrets sont masqués.

## Tests du projet

```bash
python -m pytest -q
python -m ruff check src tests    # vérification du style
```

## Limites connues

- Si la spécification contient une section `servers:`, elle remplace `api_url`.
- L'agent ignore tout argument en ligne de commande : tout passe par `config.json`.
- La clé `model_options.max_endpoints` apparaît dans la configuration mais n'est pas implémentée. Elle est ignorée sans avertissement.

## Licence

MIT.
