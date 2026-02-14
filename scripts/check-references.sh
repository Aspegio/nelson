#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="skills/nelson"
REF_DIR="$SKILL_DIR/references"
errors=0

error() {
  echo "ERROR: $1" >&2
  errors=$((errors + 1))
}

# ---------- 1. SKILL.md → references ----------
# Every backtick-quoted references/ path in SKILL.md must exist
echo "Checking SKILL.md → reference files..."
while IFS= read -r path; do
  if [ ! -f "$SKILL_DIR/$path" ]; then
    error "SKILL.md references '$path' but $SKILL_DIR/$path does not exist"
  fi
done < <(grep -oE '`references/[^`]+\.md`' "$SKILL_DIR/SKILL.md" \
  | tr -d '`' \
  | sort -u)

# ---------- 2. Subdirectory orphan check ----------
# Every .md in a subdirectory must be referenced somewhere in SKILL.md
echo "Checking for orphaned subdirectory files..."
for subdir in admiralty-templates standing-orders damage-control; do
  [ -d "$REF_DIR/$subdir" ] || continue
  for file in "$REF_DIR/$subdir"/*.md; do
    [ -f "$file" ] || continue
    basename=$(basename "$file")
    if ! grep -qE "\`references/${subdir}/${basename}\`" "$SKILL_DIR/SKILL.md"; then
      error "$subdir/$basename exists on disk but is not referenced in SKILL.md"
    fi
  done
done

# ---------- 3. Reference file cross-refs ----------
# Backtick-quoted paths in top-level reference files
echo "Checking cross-references in reference files..."
for ref_file in "$REF_DIR"/*.md; do
  [ -f "$ref_file" ] || continue
  basename=$(basename "$ref_file")

  # Paths like `references/foo.md` (relative to skill root)
  while IFS= read -r path; do
    if [ ! -f "$SKILL_DIR/$path" ]; then
      error "$basename references '$path' but $SKILL_DIR/$path does not exist"
    fi
  done < <(grep -oE '`references/[^`]+\.md`' "$ref_file" \
    | tr -d '`' \
    | sort -u)

  # Paths like `standing-orders/foo.md` (relative to references/)
  while IFS= read -r path; do
    if [ ! -f "$REF_DIR/$path" ]; then
      error "$basename references '$path' but $REF_DIR/$path does not exist"
    fi
  done < <(grep -oE '`(standing-orders|admiralty-templates|damage-control)/[^`]+\.md`' "$ref_file" \
    | tr -d '`' \
    | sort -u)
done

# ---------- 4. Subdirectory file cross-refs ----------
# Backtick-quoted paths in subdirectory files
echo "Checking cross-references in subdirectory files..."
for subdir in admiralty-templates standing-orders damage-control; do
  [ -d "$REF_DIR/$subdir" ] || continue
  for ref_file in "$REF_DIR/$subdir"/*.md; do
    [ -f "$ref_file" ] || continue
    basename=$(basename "$ref_file")

    # Paths like `references/foo.md` (relative to skill root)
    while IFS= read -r path; do
      if [ ! -f "$SKILL_DIR/$path" ]; then
        error "$subdir/$basename references '$path' but $SKILL_DIR/$path does not exist"
      fi
    done < <(grep -oE '`references/[^`]+\.md`' "$ref_file" \
      | tr -d '`' \
      | sort -u)

    # Paths like `standing-orders/foo.md` (relative to references/)
    while IFS= read -r path; do
      if [ ! -f "$REF_DIR/$path" ]; then
        error "$subdir/$basename references '$path' but $REF_DIR/$path does not exist"
      fi
    done < <(grep -oE '`(standing-orders|admiralty-templates|damage-control)/[^`]+\.md`' "$ref_file" \
      | tr -d '`' \
      | sort -u)
  done
done

# ---------- 5. Reverse orphan check ----------
# Every top-level .md in references/ should be referenced by SKILL.md
echo "Checking for unreferenced top-level reference files..."
for ref_file in "$REF_DIR"/*.md; do
  [ -f "$ref_file" ] || continue
  basename=$(basename "$ref_file")

  if ! grep -qE "\`references/${basename}\`" "$SKILL_DIR/SKILL.md"; then
    error "$basename exists in references/ but is not referenced in SKILL.md"
  fi
done

# ---------- Summary ----------
if [ "$errors" -gt 0 ]; then
  echo ""
  echo "FAILED: $errors broken reference(s) found"
  exit 1
else
  echo ""
  echo "OK: All cross-references are valid"
  exit 0
fi
