#!/usr/bin/env bash
# One-command Claudeville launcher (Git Bash on Windows, or Linux/WSL).
#
# Encodes the operational gotchas:
#   - frees :5000 / :8000 (Windows leaves detached python processes),
#   - starts the Flask backend (autosim) and feeds the startup prompt a newline so it
#     begins a fresh sim from local_config.json's default_fork (stdin kept open),
#   - starts the Django frontend with DJANGO_DEBUG=True (REQUIRED, else /static/ 404s
#     -> black screen + green sprite placeholders).
#
# Usage: ./scripts/run_claudeville.sh
# One-time on Windows (long the_ville asset paths): git config core.longpaths true
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/env/Scripts/python.exe"; [ -x "$PY" ] || PY="$ROOT/env/bin/python"

free_port() {
  for pid in $(netstat -ano 2>/dev/null | grep LISTENING | grep ":$1 " | awk '{print $NF}' | sort -u); do
    taskkill //PID "$pid" //F >/dev/null 2>&1 || kill -9 "$pid" 2>/dev/null || true
  done
  command -v lsof >/dev/null 2>&1 && lsof -ti:"$1" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
}
echo "Freeing :5000 / :8000 ..."
free_port 5000; free_port 8000; sleep 1

echo "Starting backend (Flask + autosim) ..."
( cd "$ROOT/reverie/backend_server" && { printf '\n'; exec tail -f /dev/null; } | \
  env PYTHONUTF8=1 PYTHONIOENCODING=utf-8 CLAUDEVILLE_PERSONA_MOVE_TIMEOUT=120 \
  "$PY" -u reverie.py > /tmp/cv_backend.log 2>&1 ) &

echo "Starting frontend (Django, DJANGO_DEBUG=True) ..."
( cd "$ROOT/environment/frontend_server" && \
  env PYTHONUTF8=1 DJANGO_DEBUG=True "$PY" -u manage.py runserver 8000 --noreload \
  > /tmp/cv_frontend.log 2>&1 ) &

echo ""
echo "Booting... open http://localhost:8000/simulator_home"
echo "(First Play step is LLM-bound ~1-2 min, shown as 'Buffering'; logs: /tmp/cv_backend.log, /tmp/cv_frontend.log)"
