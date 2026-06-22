#!/usr/bin/env bash
# Idempotent GitHub configuration for marginalia: branch protection + labels.
# The ONLY way repo config is changed. Re-run after editing required contexts or labels.
# Requires: gh auth login. Usage: bash scripts/setup-github.sh
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-VforVitorio/marginalia}"

# Exact CI job names that must pass before merge (see .github/workflows/ci.yml).
REQUIRED_CONTEXTS=(test lint typecheck frontend-build)

# "name|color|description"
LABELS=(
  "bug|d73a4a|Something isn't working"
  "enhancement|a2eeef|New feature or request"
  "infra|0e8a16|Build, CI, or tooling"
  "dependencies|0366d6|Dependency updates"
  "do-not-rebase|fbca04|Skip auto-update of this PR"
  "area: api|1d76db|Backend HTTP layer"
  "area: backend|5319e7|Python backend"
  "area: frontend|bfd4f2|React frontend"
  "area: ocr|c2e0c6|OCR engines"
  "area: docs|0075ca|Documentation"
  "area: ci-cd|cccccc|CI/CD and workflows"
  "area: deps|e4e669|Dependencies"
  "priority:high|b60205|High priority"
  "priority:low|c5def5|Low priority"
)

protection_payload() {
  local contexts
  contexts=$(printf '"%s",' "${REQUIRED_CONTEXTS[@]}" | sed 's/,$//')
  cat <<EOF
{
  "required_status_checks": {"strict": true, "contexts": [${contexts}]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "required_conversation_resolution": true,
  "restrictions": null,
  "lock_branch": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
}

echo "Applying branch protection to ${REPO}:main ..."
gh api -X PUT "repos/${REPO}/branches/main/protection" --input - <<<"$(protection_payload)" >/dev/null
echo "  done."

echo "Creating/updating labels ..."
for entry in "${LABELS[@]}"; do
  IFS='|' read -r name color desc <<<"$entry"
  gh label create "$name" --color "$color" --description "$desc" --force >/dev/null
  echo "  - ${name}"
done

echo "GitHub setup complete."
