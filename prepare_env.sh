#!/usr/bin/env bash
# подготовка окружения: выполняется один раз, вне лимита запуска run.py
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
MIN_VERSION="3.10"

if ! "$PYTHON" -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)" 2>/dev/null; then
    echo "Нужен Python $MIN_VERSION или новее, найден: $("$PYTHON" -V 2>&1)" >&2
    echo "Укажите интерпретатор явно: PYTHON=python3.11 ./prepare_env.sh" >&2
    exit 1
fi

if [ ! -d "$ROOT/.venv" ]; then
    "$PYTHON" -m venv "$ROOT/.venv"
fi

"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" "$ROOT/download_models.py" --out "$ROOT/models"

echo "Окружение готово: $ROOT/.venv"
