#!/usr/bin/env bash
# Deprecated — use scripts/create-regression-pr.sh (also: task regression:pr).
exec "$(dirname "$0")/create-regression-pr.sh" "$@"
