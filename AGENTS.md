# Repository Guidelines

## Project Structure & Module Organization
Claudeville is a Python simulation project with a Django frontend and Flask-backed simulation runtime. Core backend logic lives in `reverie/backend_server/`, with persona behavior under `persona/`, memory structures under `persona/memory_structures/`, and Claude Agent SDK prompting in `persona/prompt_template/claude_structure.py`. The browser UI is in `environment/frontend_server/`; Django settings and URLs live in `frontend_server/`, templates in `templates/`, CSS and game assets in `static_dirs/`, and simulation state in `storage/`.

## Build, Test, and Development Commands
- `./start.sh`: create or reuse the `claudeville` Conda environment, run migrations, start Django on `localhost:8000`, then start the backend CLI/API.
- `conda env create -f environment.yaml`: install the project environment manually.
- `conda activate claudeville`: activate dependencies before running Python commands.
- `python environment/frontend_server/manage.py test`: run Django tests.
- `ruff check .` and `ruff format .`: lint and format Python files.

## Coding Style & Naming Conventions
Use Python 3.9-3.11, four-space indentation, and `snake_case` for modules, functions, variables, and JSON-style simulation fields. Keep Django app code inside `environment/frontend_server/` and simulation/persona code inside `reverie/backend_server/`. Ruff enforces `E`, `F`, and `W` rules; line length is intentionally not enforced by `E501`.

## Testing Guidelines
Current test coverage is minimal (`environment/frontend_server/translator/tests.py`). Add Django tests near the app they exercise and name test methods `test_<behavior>`. For backend simulation changes, prefer focused unit tests for pure helpers and document any manual simulator checks performed through `./start.sh`.

## Commit & Pull Request Guidelines
Recent commits use short, imperative summaries such as `Fix conversation range check too aggressive` and `Tiered perception system and position fixes`. Follow that style: one concise subject, no trailing period. Pull requests should describe behavior changes, list verification commands, link related issues, and include screenshots or short recordings for UI changes.

## Security & Configuration Tips
Do not commit Claude credentials, generated logs, or local simulation runs. Keep large generated assets out of commits unless they are intentional source assets.
