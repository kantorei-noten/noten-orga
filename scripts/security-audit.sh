#!/usr/bin/env bash
# Sicherheits-Audit der Abhängigkeiten (pip-audit) + optional Trivy-Dateisystemscan.
set -uo pipefail
cd "$(dirname "$0")/.."

echo "== pip-audit (Python-Abhängigkeiten) =="
uv run --with pip-audit pip-audit || true

echo
echo "== Trivy (Dateisystem, falls installiert) =="
if command -v trivy >/dev/null 2>&1; then
  trivy fs --quiet --scanners vuln .
else
  echo "trivy nicht installiert — übersprungen (Install: https://aquasecurity.github.io/trivy)"
fi
