#!/usr/bin/env bash
# Demo Database Setup
# Builds schemas and FAISS indices needed for hierarchical RAG demonstration
#
# This script orchestrates:
#   1. build_schema.py - Extract parameter schemas from C++ source for each code
#   2. build_all_indices.py - Build 3-level hierarchical indices (L0, L1, L2)
#   3. build_index.py - Build simple per-code indices
#
# Usage:
#   bash demo/setup_demo_database.sh                    # Build missing indices only
#   bash demo/setup_demo_database.sh --force-rebuild   # Force rebuild everything
#   bash demo/setup_demo_database.sh --code erf         # Build ERF only
#   bash demo/setup_demo_database.sh --code amrex       # Build AMReX only
#   bash demo/setup_demo_database.sh --code pelelmex    # Build PeleLMeX only
#   bash demo/setup_demo_database.sh --upload-openai    # Upload docs to OpenAI vector store
#   bash demo/setup_demo_database.sh --mock             # Use mock embeddings (no API calls)
#   bash demo/setup_demo_database.sh --clone-missing    # Clone missing repos (requires network)
#
# Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.

set -euo pipefail

log() {
  if [[ $# -eq 0 || ( $# -eq 1 && -z "$1" ) ]]; then
    echo ""
    return
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

FORCE_REBUILD=0
TARGET_CODE="all"
UPLOAD_OPENAI=0
USE_MOCK=0
CLONE_MISSING=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-rebuild)
      FORCE_REBUILD=1
      shift
      ;;
    --mock)
      USE_MOCK=1
      shift
      ;;
    --clone-missing)
      CLONE_MISSING=1
      shift
      ;;
    --code)
      TARGET_CODE="$2"
      shift 2
      ;;
    --code=*)
      TARGET_CODE="${1#*=}"
      shift
      ;;
    --upload-openai)
      UPLOAD_OPENAI=1
      shift
      ;;
    *)
      log "Unknown argument: $1"
      exit 1
      ;;
  esac
done

TARGET_CODE="${TARGET_CODE,,}"

should_process() {
  local code="$1"
  if [[ "$TARGET_CODE" == "all" ]]; then
    return 0
  fi
  [[ "$TARGET_CODE" == "$code" ]]
}

schema_exists() {
  local code="$1"
  local pattern1="database/schemas/${code}_schema_*.json"
  local pattern2="database/schemas/${code}_complete_*.json"
  shopt -s nullglob
  local matches=($pattern1)
  matches+=($pattern2)
  shopt -u nullglob
  (( ${#matches[@]} > 0 ))
}

if [[ "$TARGET_CODE" != "all" ]]; then
  case "$TARGET_CODE" in
    pelec|pelelmex|erf|amrex)
      ;;
    *)
      log "Unsupported --code: $TARGET_CODE (expected pelec, pelelmex, erf, amrex, or all)"
      exit 1
      ;;
  esac
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

log "===================================================="
log "Demo Database Setup"
log "===================================================="
log ""

if [[ $FORCE_REBUILD -eq 1 ]]; then
  log "Mode: FORCE REBUILD (all indices)"
else
  log "Mode: BUILD MISSING (incremental - reuses existing indices)"
fi

log "Code filter: $TARGET_CODE"
log "Upload to OpenAI: $UPLOAD_OPENAI"
if [[ $USE_MOCK -eq 1 ]]; then
  log "Embedding mode: MOCK (no API calls)"
else
  log "Embedding mode: REAL (API key required)"
fi
if [[ $CLONE_MISSING -eq 1 ]]; then
  log "Repo mode: CLONE MISSING (requires git + network)"
else
  log "Repo mode: USE EXISTING"
fi
log ""
log "This will build:"
log ""
log "1. SCHEMAS (from C++ source):"
log "   - Parameter schemas for available codes (PeleC, PeleLMeX, ERF, AMReX)"
log ""
log "2. HIERARCHICAL INDICES:"
log "   - Level 0: Solver selection (4 indices)"
log "   - Level 1: Documentation per solver"
log "   - Level 2: Case metadata per solver (7 types × solvers)"
log ""
log "3. SIMPLE INDICES (per code):"
log "   - case_structure, case_details, input_templates, chemistry, case_names"
log ""

# Code paths (adjust as needed)
PELEC_PATH="${PELEC_REPO_PATH:-${PELEC_PATH:-../PeleC}}"
PELELMEX_PATH="${PELELMEX_REPO_PATH:-${PELELMEX_PATH:-../PeleLMeX}}"
ERF_PATH="${ERF_REPO_PATH:-${ERF_PATH:-../ERF}}"
AMREX_PATH="${AMREX_REPO_PATH:-${AMREX_PATH:-../amrex}}"

ensure_repo() {
  local code="$1"
  local path="$2"
  local url="$3"
  if [[ -d "$path" ]]; then
    return 0
  fi
  if [[ $CLONE_MISSING -eq 0 ]]; then
    return 1
  fi
  if ! command -v git >/dev/null 2>&1; then
    log "  ⚠️  git not found (cannot clone $code)"
    return 1
  fi
  log "  Cloning $code into $path..."
  if git clone --recursive "$url" "$path"; then
    log "  ✓ $code clone complete"
    return 0
  fi
  log "  ⚠️  $code clone failed"
  return 1
}

log ""
log "[Step 1/3] Building parameter schemas..."
log "============================================"

if should_process "pelec"; then
  if ensure_repo "PeleC" "$PELEC_PATH" "https://github.com/AMReX-Combustion/PeleC.git"; then
    if [[ $FORCE_REBUILD -eq 1 ]] || ! schema_exists "pelec"; then
      log "  Building PeleC schema..."
      python database/scripts/build_schema.py "$PELEC_PATH" --output database/schemas --auto-compose \
        && log "  ✓ PeleC schema complete" || log "  ⚠️  PeleC schema had issues"
    else
      log "  PeleC schema exists - skipping"
    fi
  else
    log "  ⚠️  PeleC source not found at $PELEC_PATH (skipping)"
  fi
fi

if should_process "pelelmex"; then
  if ensure_repo "PeleLMeX" "$PELELMEX_PATH" "https://github.com/AMReX-Combustion/PeleLMeX.git"; then
    if [[ $FORCE_REBUILD -eq 1 ]] || ! schema_exists "pelelmex"; then
      log "  Building PeleLMeX schema..."
      python database/scripts/build_schema.py "$PELELMEX_PATH" --output database/schemas --auto-compose \
        && log "  ✓ PeleLMeX schema complete" || log "  ⚠️  PeleLMeX schema had issues"
    else
      log "  PeleLMeX schema exists - skipping"
    fi
  else
    log "  ⚠️  PeleLMeX source not found at $PELELMEX_PATH (skipping)"
  fi
fi

if should_process "erf"; then
  if ensure_repo "ERF" "$ERF_PATH" "https://github.com/erf-model/ERF.git"; then
    if [[ $FORCE_REBUILD -eq 1 ]] || ! schema_exists "erf"; then
      log "  Building ERF schema..."
      python database/scripts/build_schema.py "$ERF_PATH" --output database/schemas --auto-compose \
        && log "  ✓ ERF schema complete" || log "  ⚠️  ERF schema had issues"
    else
      log "  ERF schema exists - skipping"
    fi
  else
    log "  ⚠️  ERF source not found at $ERF_PATH (skipping)"
  fi
fi

if should_process "amrex"; then
  if ensure_repo "AMReX" "$AMREX_PATH" "https://github.com/AMReX-Codes/amrex.git"; then
    if [[ $FORCE_REBUILD -eq 1 ]] || ! schema_exists "amrex"; then
      log "  Building AMReX schema..."
      python database/scripts/build_schema.py "$AMREX_PATH" --output database/schemas --auto-compose \
        && log "  ✓ AMReX schema complete" || log "  ⚠️  AMReX schema had issues"
    else
      log "  AMReX schema exists - skipping"
    fi
  else
    log "  ⚠️  AMReX source not found at $AMREX_PATH (skipping)"
  fi
fi

log ""
log "[Step 2/3] Building hierarchical indices (L0, L1, L2)..."
log "============================================"

MOCK_ARGS=()
if [[ $USE_MOCK -eq 1 ]]; then
  MOCK_ARGS=(--mock)
fi

BUILD_L0=1
if [[ $FORCE_REBUILD -eq 0 ]]; then
  L0_COUNT=$(find database/faiss/level0 -name '*.faiss' 2>/dev/null | wc -l || true)
  if [[ $L0_COUNT -eq 4 ]]; then
    log "  Level 0 indices exist (4 found) - skipping"
    BUILD_L0=0
  fi
fi

if [[ $BUILD_L0 -eq 1 ]]; then
  log "  Building Level 0 indices (solver selection)..."
  python database/scripts/build_all_indices.py --level 0 --output database/faiss "${MOCK_ARGS[@]}" \
    && log "  ✓ Level 0 complete" || log "  ✗ Level 0 FAILED"
fi

build_solver_level12() {
  local name="$1"
  local repo="$2"
  if [[ ! -d "$repo" ]]; then
    log "  ⚠️  ${name} source not found at $repo (skipping)"
    return
  fi

  local flag_var="${name^^}_L1"
  local count_l1
  local count_l2
  count_l1=$(find database/faiss/level1 -name "${name,,}_*.faiss" 2>/dev/null | wc -l || true)
  count_l2=$(find database/faiss/level2 -name "${name,,}_*.faiss" 2>/dev/null | wc -l || true)

  if [[ $FORCE_REBUILD -eq 0 && $count_l1 -gt 0 && $count_l2 -gt 0 ]]; then
    log "  ${name} Level 1 & 2 indices exist - skipping"
    return
  fi

  log "  Building ${name} Level 1 & 2 indices..."
  python database/scripts/build_all_indices.py --level 1 --repo "$repo" --output database/faiss "${MOCK_ARGS[@]}" \
    && log "    ✓ ${name} Level 1 complete" || log "    ⚠️  ${name} Level 1 had issues"
  python database/scripts/build_all_indices.py --level 2 --repo "$repo" --output database/faiss "${MOCK_ARGS[@]}" \
    && log "    ✓ ${name} Level 2 complete" || log "    ⚠️  ${name} Level 2 had issues"
}

if should_process "pelec"; then
  build_solver_level12 "PeleC" "$PELEC_PATH"
fi

if should_process "pelelmex"; then
  build_solver_level12 "PeleLMeX" "$PELELMEX_PATH"
fi

if should_process "erf"; then
  build_solver_level12 "ERF" "$ERF_PATH"
fi

if should_process "amrex"; then
  log "  AMReX hierarchical indices are not built by default (simple indices only)"
fi

log ""
log "[Step 3/3] Building simple per-code indices..."
log "============================================"

SIMPLE_TYPES=(
  "case_structure"
  "case_details"
  "input_templates"
  "chemistry"
  "case_names"
)

build_simple_indices() {
  local code="$1"
  local repo="$2"
  if [[ $USE_MOCK -eq 1 ]]; then
    log "  Skipping $code simple indices in mock mode (real embeddings required)"
    return
  fi
  if [[ ! -d "$repo" ]]; then
    log "  ⚠️  $code source not found at $repo (skipping simple indices)"
    return
  fi

  local prefix="${code,,}"
  local count
  count=$(find database/faiss -maxdepth 2 -path "*${prefix}_*/index.faiss" 2>/dev/null | wc -l || true)
  if [[ $FORCE_REBUILD -eq 0 && $count -ge 3 ]]; then
    log "  $code simple indices exist ($count found) - skipping"
    return
  fi

  log "  Building $code simple indices..."
  for type in "${SIMPLE_TYPES[@]}"; do
    log "    - ${type}..."
    python database/scripts/build_index.py --type ${type} --config ${code,,} --embedding cborg --source "$repo" \
      && log "      ✓" || log "      ✗ FAILED"
  done
}

if should_process "pelec"; then
  build_simple_indices PeleC "$PELEC_PATH"
fi

if should_process "pelelmex"; then
  build_simple_indices PeleLMeX "$PELELMEX_PATH"
fi

if should_process "erf"; then
  build_simple_indices ERF "$ERF_PATH"
fi

if should_process "amrex"; then
  build_simple_indices AMReX "$AMREX_PATH"
fi

log ""
log "===================================================="
log "Validating Database"
log "===================================================="
log ""

if [[ -d "database/schemas" ]]; then
  log "Schemas:"
  SCHEMA_COUNT=$(find database/schemas -name '*.json' 2>/dev/null | wc -l || true)
  log "  $SCHEMA_COUNT schema files"
else
  log "Schemas:"
  log "  (not built)"
fi

log ""
log "Indices:"
if [[ -d "database/faiss" ]]; then
  L0_COUNT=$(find database/faiss/level0 -name '*.faiss' 2>/dev/null | wc -l || true)
  L1_COUNT=$(find database/faiss/level1 -name '*.faiss' 2>/dev/null | wc -l || true)
  L2_COUNT=$(find database/faiss/level2 -name '*.faiss' 2>/dev/null | wc -l || true)
  SIMPLE_COUNT=$(find database/faiss -maxdepth 2 -name 'index.faiss' 2>/dev/null | wc -l || true)

  log "  Level 0 (Solver selection):    $L0_COUNT indices (4 expected)"
  log "  Level 1 (Documentation):       $L1_COUNT indices"
  log "  Level 2 (Case metadata):       $L2_COUNT indices"
  log "  Simple (Code-specific):        $SIMPLE_COUNT indices"

  log ""
  log "Breakdown by code:"
  log "  PeleC:    $(find database/faiss -maxdepth 2 -path '*pelec_*/index.faiss' 2>/dev/null | wc -l || true) indices"
  log "  PeleLMeX: $(find database/faiss -maxdepth 2 -path '*pelelmex_*/index.faiss' 2>/dev/null | wc -l || true) indices"
  log "  ERF:      $(find database/faiss -maxdepth 2 -path '*erf_*/index.faiss' 2>/dev/null | wc -l || true) indices"
  log "  AMReX:    $(find database/faiss -maxdepth 2 -path '*amrex_*/index.faiss' 2>/dev/null | wc -l || true) indices"
else
  log "  (not built)"
fi

log ""
log "===================================================="
log "Database Setup Complete!"
log "===================================================="
log ""
if [[ $UPLOAD_OPENAI -eq 1 ]]; then
  log "[Optional] Uploading documents to OpenAI vector store..."
  log "============================================"
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    log "  ⚠️  OPENAI_API_KEY not set; cannot upload"
  else
    bash demo/vector_store/upload_openai_vector_store.sh --config "$TARGET_CODE" --type all
    log "  ✓ OpenAI upload complete"
  fi
  log ""
fi
log "Next steps:"
log "  1. Run the demo examples:"
log "     bash demo/run_examples.sh"
log ""
log "  2. Monitor progress:"
log "     tail -f examples/*/generation.log"
log ""
