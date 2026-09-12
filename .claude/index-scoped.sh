#!/usr/bin/env bash
set -euo pipefail
gitnexus() {
  command gitnexus "$@" --index-only --skip-git --name menuplan-complete-dish-data-0908
}
export -f gitnexus
exec /usr/local/bin/gitnexus-reindex /nvmetank1/projects/menuplan/.claude/worktrees/complete-dish-data-0908
