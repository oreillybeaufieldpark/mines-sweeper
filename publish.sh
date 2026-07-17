#!/usr/bin/env bash
set -euo pipefail

cd /home/foreilly/PGA2026
source /home/foreilly/golf-sweep/.venv/bin/activate

python3 match_test.py

git add index.html matched_leaderboard.json match_test.py config.json owners.csv

if git diff --cached --quiet; then
  echo "No changes"
else
  git commit -m "Update leaderboard"
  git push
fi
