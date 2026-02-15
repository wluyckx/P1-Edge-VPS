#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PATTERN='BEGIN (RSA|OPENSSH|EC|DSA)? ?PRIVATE KEY|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk_live_[0-9A-Za-z]{20,}|rk_live_[0-9A-Za-z]{20,}|AIza[0-9A-Za-z\-_]{35}|SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}|-----BEGIN CERTIFICATE-----'

echo "Running secret scan on tracked files..."

set +e
git ls-files -z | xargs -0 rg -n -I -e "${PATTERN}" >/tmp/secret_scan_hits.txt
status=$?
set -e

if [ "${status}" -eq 0 ]; then
  echo "Potential secrets detected:"
  cat /tmp/secret_scan_hits.txt
  exit 1
fi

if [ "${status}" -ne 1 ]; then
  echo "Secret scan failed to run correctly (exit code ${status})."
  exit "${status}"
fi

echo "No high-confidence secrets detected."
