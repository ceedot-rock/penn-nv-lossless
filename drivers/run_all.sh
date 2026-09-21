#!/bin/bash
# Quantum-bench driver: text files first (CSVs, txt, code), then .mat smallest-first.
# Appends TSV rows to results/results.tsv. Safe to re-run: skips files with a pcc row.
set -u
D="$HOME/workspace/quantum-bench/data"
RDIR="$HOME/workspace/quantum-bench/results"
H="$HOME/workspace/pcc-weights-bench"
LOG="$RDIR/results.tsv"
mkdir -p "$RDIR"
[ -f "$LOG" ] || printf "tag\tmethod\torig\tcomp\tratio\tenc_s\tdec_s\tsha\tnote\n" > "$LOG"

list="$RDIR/filelist.txt"
: > "$list"
find "$D" -type f \( -name '*.csv' -o -name '*.txt' -o -name '*.py' -o -name '*.ipynb' -o -name '*.mplstyle' \) ! -path '*__MACOSX*' ! -name '.DS_Store' | sort >> "$list"
find "$D" -type f -name '*.mat' ! -path '*__MACOSX*' | while IFS= read -r f; do stat -c "%s %n" "$f"; done | sort -n | cut -d' ' -f2- >> "$list"

total=$(wc -l < "$list")
echo "files queued: $total"
i=0
while IFS= read -r f; do
  i=$((i+1))
  tag=$(echo "$f" | sed "s|$D/||; s|/|__|g; s| |_|g")
  if grep -q "^${tag}	pcc	" "$LOG"; then echo "[$i/$total] SKIP $tag"; continue; fi
  echo "[$i/$total] BENCH $f"
  bash "$HOME/workspace/quantum-bench/bench_one_q.sh" "$f" "$RDIR" "$tag"
done < "$list"
echo ALLDONE > "$RDIR/DONE"
echo "=== ALL DONE ==="
