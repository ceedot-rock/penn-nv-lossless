#!/bin/bash
# Benchmark one file across all methods. Usage: bench_one.sh <input> <results_dir> <tag>
# Appends TSV rows to $results_dir/results.tsv
set -u
IN="$1"
RDIR="$2"
TAG="$3"
BDIR="$(dirname "$0")"
# bench_one_q.sh lives in quantum-bench; the harness tools live in pcc-weights-bench
BDIR="$HOME/workspace/pcc-weights-bench"
NPCC="$BDIR/npcc-clean/bin/npcc"
PY="$BDIR/venv/bin/python"
LOG="$RDIR/results.tsv"
mkdir -p "$RDIR"

now() { date +%s%N; }
elapsed() { # $1=start_ns $2=end_ns -> seconds with 3 decimals
  python3 -c "print(f'{($2-$1)/1e9:.3f}')"
}

FNAME="$(basename "$IN")"
ORIG_BYTES=$(stat -c%s "$IN")
ORIG_SHA=$(sha256sum "$IN" | awk '{print $1}')
echo "### $TAG $FNAME orig=$ORIG_BYTES sha=${ORIG_SHA:0:16}..."

run_cell() { # $1=method $2=enc_cmd... ; enc writes to $OUT ; then generic decode+verify
  local method="$1"; shift
  local out="$RDIR/$TAG.$method.bin"
  local dec="$RDIR/$TAG.$method.dec"
  local enc_cmd="$1"
  echo "--- [$method] encoding..."
  local s=$(now)
  # shellcheck disable=SC2086
  eval "$enc_cmd" >"$RDIR/$TAG.$method.enc.log" 2>&1
  local rc=$?
  local e=$(now)
  local enc_sec=$(elapsed $s $e)
  if [ $rc -ne 0 ] || [ ! -f "$out" ]; then
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$TAG" "$method" "$ORIG_BYTES" "" "" "$enc_sec" "" "ENCODE_FAIL" "rc=$rc" >>"$LOG"
    echo "!!! [$method] ENCODE FAILED rc=$rc"
    return 1
  fi
  local comp_bytes=$(stat -c%s "$out")
  local ratio=$(python3 -c "print(f'{$comp_bytes/$ORIG_BYTES:.6f}')")
  echo "--- [$method] decoding..."
  s=$(now)
  eval "$2" >"$RDIR/$TAG.$method.dec.log" 2>&1
  rc=$?
  e=$(now)
  local dec_sec=$(elapsed $s $e)
  local sha_ok="DECODE_FAIL"
  if [ $rc -eq 0 ] && [ -f "$dec" ]; then
    local dsha=$(sha256sum "$dec" | awk '{print $1}')
    if [ "$dsha" = "$ORIG_SHA" ]; then sha_ok="OK"; else sha_ok="MISMATCH"; fi
    rm -f "$dec"
  fi
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$TAG" "$method" "$ORIG_BYTES" "$comp_bytes" "$ratio" "$enc_sec" "$dec_sec" "$sha_ok" "" >>"$LOG"
  echo "[$method] comp=$comp_bytes ratio=$ratio enc=${enc_sec}s dec=${dec_sec}s sha=$sha_ok"
  # keep compressed outputs for the paper appendix; comment out to save space
  return 0
}

O="$RDIR/$TAG"

run_cell "gzip-9"  "gzip -9 -c \"$IN\" > \"$O.gzip-9.bin\""      "gzip -dc \"$O.gzip-9.bin\" > \"$O.gzip-9.dec\""
run_cell "xz-6"    "xz -6 -c \"$IN\" > \"$O.xz-6.bin\""          "xz -dc \"$O.xz-6.bin\" > \"$O.xz-6.dec\""
run_cell "zstd-3"  "\"$PY\" \"$BDIR/zstd_helper.py\" c 3 \"$IN\" \"$O.zstd-3.bin\""  "\"$PY\" \"$BDIR/zstd_helper.py\" d 3 \"$O.zstd-3.bin\" \"$O.zstd-3.dec\""
run_cell "zstd-19" "\"$PY\" \"$BDIR/zstd_helper.py\" c 19 \"$IN\" \"$O.zstd-19.bin\"" "\"$PY\" \"$BDIR/zstd_helper.py\" d 19 \"$O.zstd-19.bin\" \"$O.zstd-19.dec\""

echo "--- [pcc] encoding (watchdog: 20min stall kill, 2h abs cap)..."
PO="$O.pcc.bin"; PD="$O.pcc.dec"
s=$(now)
QBDIR="$HOME/workspace/quantum-bench"
watch_msg=$(bash "$QBDIR/pcc_watch.sh" "$IN" "$PO" "$RDIR/$TAG.pcc.enc.log" 2>&1)
rc=$?
e=$(now)
enc_sec=$(elapsed $s $e)
if [ $rc -ne 0 ] || [ ! -f "$PO" ]; then
  note="rc=$rc msg=$watch_msg"
  [ "$rc" = "124" ] && note="STALLED_20min_no_progress"
  [ "$rc" = "125" ] && note="TIMEOUT_2h_absolute"
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$TAG" "pcc" "$ORIG_BYTES" "" "" "$enc_sec" "" "ENCODE_FAIL" "$note" >>"$LOG"
  echo "!!! [pcc] ENCODE FAILED: $note (killed/hung - no result)"
else
  comp_bytes=$(stat -c%s "$PO")
  ratio=$(python3 -c "print(f'{$comp_bytes/$ORIG_BYTES:.6f}')")
  echo "--- [pcc] decoding..."
  s=$(now)
  "$NPCC" d "$PO" "$PD" >"$RDIR/$TAG.pcc.dec.log" 2>&1
  rc=$?
  e=$(now); dec_sec=$(elapsed $s $e)
  sha_ok="DECODE_FAIL"
  if [ $rc -eq 0 ] && [ -f "$PD" ]; then
    dsha=$(sha256sum "$PD" | awk '{print $1}')
    if [ "$dsha" = "$ORIG_SHA" ]; then sha_ok="OK"; else sha_ok="MISMATCH"; fi
    rm -f "$PD"
  fi
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$TAG" "pcc" "$ORIG_BYTES" "$comp_bytes" "$ratio" "$enc_sec" "$dec_sec" "$sha_ok" "" >>"$LOG"
  echo "[pcc] comp=$comp_bytes ratio=$ratio enc=${enc_sec}s dec=${dec_sec}s sha=$sha_ok"
fi
echo "### $TAG done"
