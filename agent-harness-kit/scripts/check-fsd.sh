#!/bin/bash
# FSD (Feature-Sliced Design) layer import enforcement.
#
# Enforces three rules:
#   FSD-001: Layer imports must flow downward only
#            app -> pages -> widgets -> features -> entities -> shared
#   FSD-002: Entity imports from outside entities/ must use barrel exports
#            e.g. @/entities/agent (ok) vs @/entities/agent/model/types (violation)
#   FSD-003: No relative imports that traverse up into a different FSD layer
#            e.g. ../../shared/lib from features/ (violation)
#
# Usage:
#   ./scripts/check-fsd.sh              # check all
#   ./scripts/check-fsd.sh --json       # JSON output for agents
#
# Exit codes:
#   0 — no violations
#   1 — violations found

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load project config
# shellcheck source=../harness.config.sh
source "$PROJECT_ROOT/harness.config.sh"

SRC_DIR="$PROJECT_ROOT/$FRONTEND_DIR/src"

JSON_MODE=false
if [[ "${1:-}" == "--json" ]]; then
  JSON_MODE=true
fi

# Colors (disabled in JSON mode)
if $JSON_MODE; then
  RED="" GREEN="" YELLOW="" BLUE="" NC=""
else
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  BLUE='\033[0;34m'
  NC='\033[0m'
fi

VIOLATIONS=0
VIOLATION_LINES=()

violation() {
  local rule="$1" file="$2" line_num="$3" message="$4" import_line="$5"
  VIOLATIONS=$((VIOLATIONS + 1))
  local rel_file="${file#$PROJECT_ROOT/}"
  if $JSON_MODE; then
    VIOLATION_LINES+=("{\"rule\":\"$rule\",\"file\":\"$rel_file\",\"line\":$line_num,\"message\":\"$message\",\"import\":\"$import_line\"}")
  else
    echo -e "  ${RED}$rule${NC} $rel_file:$line_num"
    echo -e "    ${YELLOW}$message${NC}"
    echo -e "    ${BLUE}$import_line${NC}"
  fi
}

# FSD layer hierarchy — index = rank (lower = deeper, can be imported by higher)
# Layer name -> allowed import targets (everything with lower or equal rank)
declare -A LAYER_RANK=(
  [app]=5
  [pages]=4
  [widgets]=3
  [features]=2
  [entities]=1
  [shared]=0
)

# Map @/ import prefixes to FSD layers
get_layer_from_import() {
  local import_path="$1"
  # Match @/layer/... pattern
  if [[ "$import_path" =~ ^@/(app|pages|widgets|features|entities|shared)(/|$) ]]; then
    echo "${BASH_REMATCH[1]}"
    return 0
  fi
  # @/components and @/lib are treated as shared-level
  if [[ "$import_path" =~ ^@/(components|lib)(/|$) ]]; then
    echo "shared"
    return 0
  fi
  echo ""
  return 1
}

get_layer_from_filepath() {
  local filepath="$1"
  local rel="${filepath#$SRC_DIR/}"
  local first_segment="${rel%%/*}"
  case "$first_segment" in
    app|pages|widgets|features|entities|shared) echo "$first_segment" ;;
    components|lib) echo "shared" ;;
    *) echo "" ;;
  esac
}

# --- FSD-001: Layer direction ---
check_layer_direction() {
  local file="$1" source_layer="$2"
  local source_rank="${LAYER_RANK[$source_layer]:-}"
  if [[ -z "$source_rank" ]]; then
    return
  fi

  while IFS=: read -r line_num line_content; do
    # Match import/export statements including multiline closing braces.
    # Single-line: import { X } from '@/...'
    # Multiline closing: } from '@/...'
    # Skip comments (lines starting with // or *)
    if [[ "$line_content" =~ ^[[:space:]]*(//|\*) ]]; then
      continue
    fi

    # Extract import path from: import ... from '@/...' or export ... from '@/...'
    local import_path=""
    if [[ "$line_content" =~ from\ [\'\"](@/[^\'\"]+)[\'\"] ]]; then
      import_path="${BASH_REMATCH[1]}"
    elif [[ "$line_content" =~ import\ [\'\"](@/[^\'\"]+)[\'\"] ]]; then
      import_path="${BASH_REMATCH[1]}"
    fi

    if [[ -z "$import_path" ]]; then
      continue
    fi

    local target_layer
    target_layer=$(get_layer_from_import "$import_path") || continue
    if [[ -z "$target_layer" ]]; then
      continue
    fi

    local target_rank="${LAYER_RANK[$target_layer]:-}"
    if [[ -z "$target_rank" ]]; then
      continue
    fi

    # Violation: importing from a layer with higher or equal rank (except same layer)
    if [[ "$target_layer" != "$source_layer" ]] && (( target_rank >= source_rank )); then
      violation "FSD-001" "$file" "$line_num" \
        "Layer '$source_layer' cannot import from '$target_layer' — imports must flow downward: app > pages > widgets > features > entities > shared" \
        "$line_content"
    fi
  done < <(grep -nE "from ['\"]@/" "$file" 2>/dev/null || true)
}

# --- FSD-002: Entity barrel exports ---
check_entity_barrel_exports() {
  local file="$1" source_layer="$2"
  # Only check files OUTSIDE entities/
  if [[ "$source_layer" == "entities" ]]; then
    return
  fi

  while IFS=: read -r line_num line_content; do
    # Only match actual import/export statements, not comments
    if [[ ! "$line_content" =~ ^[[:space:]]*(import|export) ]]; then
      continue
    fi

    local import_path=""
    if [[ "$line_content" =~ from\ [\'\"](@/entities/[^\'\"]+)[\'\"] ]]; then
      import_path="${BASH_REMATCH[1]}"
    fi

    if [[ -z "$import_path" ]]; then
      continue
    fi

    # @/entities/agent is fine (barrel), @/entities/agent/model/types is a violation
    # Count slashes after @/entities/ — barrel has exactly one segment after entities/
    local after_entities="${import_path#@/entities/}"
    if [[ "$after_entities" == *"/"* ]]; then
      violation "FSD-002" "$file" "$line_num" \
        "Import from entity internals — use barrel export instead (e.g. '@/entities/${after_entities%%/*}')" \
        "$line_content"
    fi
  done < <(grep -nE "from ['\"]@/entities/" "$file" 2>/dev/null || true)
}

# --- FSD-003: No relative cross-layer traversal ---
check_relative_cross_layer() {
  local file="$1" source_layer="$2"

  while IFS=: read -r line_num line_content; do
    # Only match actual import/export statements, not comments
    if [[ ! "$line_content" =~ ^[[:space:]]*(import|export) ]]; then
      continue
    fi

    local import_path=""
    if [[ "$line_content" =~ from\ [\'\"](\.\.\/[^\'\"]+)[\'\"] ]]; then
      import_path="${BASH_REMATCH[1]}"
    fi

    if [[ -z "$import_path" ]]; then
      continue
    fi

    # Resolve the relative path to see if it crosses an FSD layer boundary
    local file_dir
    file_dir="$(dirname "$file")"
    local resolved
    resolved="$(cd "$file_dir" && realpath -m "$import_path" 2>/dev/null || echo "")"

    if [[ -z "$resolved" || ! "$resolved" =~ $SRC_DIR ]]; then
      continue
    fi

    local target_layer
    target_layer=$(get_layer_from_filepath "$resolved")
    if [[ -n "$target_layer" && "$target_layer" != "$source_layer" ]]; then
      violation "FSD-003" "$file" "$line_num" \
        "Relative import crosses layer boundary ('$source_layer' -> '$target_layer') — use path alias '@/' instead" \
        "$line_content"
    fi
  done < <(grep -nE "from ['\"]\.\./" "$file" 2>/dev/null || true)
}

# --- Main ---
if [[ ! -d "$SRC_DIR" ]]; then
  echo "Error: $SRC_DIR not found"
  exit 1
fi

if ! $JSON_MODE; then
  echo -e "${BLUE}FSD Layer Import Enforcement${NC}"
  echo -e "${BLUE}Rules: FSD-001 (layer direction), FSD-002 (barrel exports), FSD-003 (no cross-layer relative imports)${NC}"
  echo ""
fi

FILE_COUNT=0
while IFS= read -r -d '' file; do
  source_layer=$(get_layer_from_filepath "$file")
  if [[ -z "$source_layer" ]]; then
    continue
  fi

  FILE_COUNT=$((FILE_COUNT + 1))
  check_layer_direction "$file" "$source_layer"
  check_entity_barrel_exports "$file" "$source_layer"
  check_relative_cross_layer "$file" "$source_layer"
done < <(find "$SRC_DIR" \( -name '*.ts' -o -name '*.tsx' \) -print0)

if $JSON_MODE; then
  echo "{"
  echo "  \"rule_count\": 3,"
  echo "  \"file_count\": $FILE_COUNT,"
  echo "  \"violation_count\": $VIOLATIONS,"
  echo "  \"violations\": ["
  first=true
  for v in "${VIOLATION_LINES[@]:-}"; do
    if [[ -z "$v" ]]; then continue; fi
    if $first; then first=false; else echo ","; fi
    echo -n "    $v"
  done
  echo ""
  echo "  ]"
  echo "}"
else
  echo ""
  if (( VIOLATIONS == 0 )); then
    echo -e "${GREEN}FSD check passed — $FILE_COUNT files, 0 violations${NC}"
  else
    echo -e "${RED}FSD check found $VIOLATIONS violation(s) in $FILE_COUNT files${NC}"
    echo -e "Fix: move shared logic down, use barrel exports, use @/ path aliases"
  fi
fi

exit $((VIOLATIONS > 0 ? 1 : 0))
