#!/usr/bin/env bash
set -euo pipefail

cd /home/foreilly/PGA2026
source /home/foreilly/golf-sweep/.venv/bin/activate

python3 redraw_owners.py

git add owners_redraw.csv

if git diff --cached --quiet; then
  echo "No changes"
else
  git commit -m "Redraw owners after cut"
  git push
fi
