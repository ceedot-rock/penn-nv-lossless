#!/usr/bin/env python3
"""Evidence driver: PCCX 0.3.0, TNSSRC dev, Coaster smallest, Coaster fastpass
over the 76-file quantum-bench corpus. Exact selection semantics: every
encode is decoded and SHA-256 verified against the original.
Per-encode WATCHDOG: kill -9 the whole process group only when neither
output-file growth nor process-group CPU consumption is observed for 1200 s;
a slow-but-progressing encode is left to finish. Stall-killed rows are
recorded with empty comp bytes and note "killed -- no output/CPU progress
for >1200s", then continue.
Appends rows to results-arsenal.tsv. Evidence only: no commits/pushes/repos/PRs.
"""
import hashlib, os, subprocess, sys, time

RES = os.path.expanduser("~/workspace/quantum-bench/results")
FL = os.path.join(RES, "filelist.txt")
OUT = os.path.join(RES, "results-arsenal.tsv")
PREFIX = "/home/hatch/workspace/quantum-bench/data/"
WATCHDOG_S = 1200

PCCX = "/home/hatch/workspace/pccx-base/pccx-0.3.0/pccx-crate/target/release/pccx"
TNSSRC = "/home/hatch/workspace/tnssrc-dev/bin/npcc"
COAST = "/home/hatch/workspace/tnssrc-coaster/bin/npcc"

def tag(path):
    assert path.startswith(PREFIX), path
    t = path[len(PREFIX):].replace("/", "__").replace(" ", "_")
    return t

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def group_cpu(pgid):
    """Total utime+stime (clock ticks) over all live processes in the group."""
    total = 0
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/stat") as f:
                    st = f.read().rsplit(")", 1)[1].split()
                if int(st[3]) == pgid:  # pgrp field
                    total += int(st[11]) + int(st[12])
            except (OSError, ValueError, IndexError):
                continue
    except OSError:
        pass
    return total

def file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return -1

def run(cmd, timeout):
    """Hard-timeout variant (decode path). rc == 'TIMEOUT' on watchdog kill."""
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        so, se = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        so, se = p.communicate()
        rc = "TIMEOUT"
    wall = time.perf_counter() - t0
    so = so.decode("utf-8", "replace")[-2000:]
    se = se.decode("utf-8", "replace")[-2000:]
    return rc, wall, so, se

def run_encode(cmd, out_path, stall_s=WATCHDOG_S, poll_s=20):
    """Stall watchdog: kill -9 the whole process group only when neither
    output-file growth nor process-group CPU consumption has been observed
    for `stall_s` seconds. A slow-but-progressing encode is left to finish."""
    import signal
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True)
    pgid = p.pid
    last_size = file_size(out_path)
    last_cpu = group_cpu(pgid)
    last_progress = t0
    rc = None
    while True:
        try:
            rc = p.wait(timeout=poll_s)
            break
        except subprocess.TimeoutExpired:
            pass
        size = file_size(out_path)
        cpu = group_cpu(pgid)
        now = time.perf_counter()
        if size > last_size or cpu > last_cpu:
            last_progress = now
            last_size = max(last_size, size)
            last_cpu = max(last_cpu, cpu)
        if now - last_progress > stall_s:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
            rc = "TIMEOUT"
            break
    wall = time.perf_counter() - t0
    try:
        so, se = p.communicate(timeout=10)
    except Exception:
        so, se = b"", b""
    so = (so or b"").decode("utf-8", "replace")[-2000:]
    se = (se or b"").decode("utf-8", "replace")[-2000:]
    return rc, wall, so, se

def tail_err(se):
    lines = [l.strip() for l in se.strip().splitlines() if l.strip()]
    return "; ".join(lines[-2:]) if lines else "no stderr"

METHODS = [
    ("pccx",            lambda i, o: [PCCX, "encode", i, o],
                        lambda c, i, d: [PCCX, "decode", c, d]),
    ("tnssrc",          lambda i, o: [TNSSRC, "c", i, o],
                        lambda c, i, d: [TNSSRC, "d", c, d]),
    ("coaster-smallest",lambda i, o: [COAST, "coaster-smallest", i, o],
                        lambda c, i, d: [COAST, "coasterd", c, i, d]),
    ("coaster-fastpass",lambda i, o: [COAST, "coaster-fastpass", i, o],
                        lambda c, i, d: [COAST, "coasterd", c, i, d]),
]

def main():
    files = [l.rstrip("\n") for l in open(FL) if l.strip()]
    assert len(files) == 76, f"expected 76 files, got {len(files)}"
    first_tag = tag(files[0])
    assert first_tag == "codeproc__data_processing__MWExperimentData.py", first_tag
    print(f"[driver] {len(files)} files, tag rule OK", flush=True)

    fresh = not os.path.exists(OUT)
    done = set()
    if not fresh:
        for line in open(OUT):
            line = line.rstrip("\n")
            if not line or line.startswith("tag\t"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                done.add((parts[0], parts[1]))
    fh = open(OUT, "a", buffering=1)
    if fresh:
        fh.write("tag\tmethod\torig\tcomp\tratio\tenc_s\tdec_s\tsha\tnote\n")
    print(f"[driver] resuming: {len(done)} rows already present", flush=True)

    # pre-check: none of our .bin names collide with existing files
    for f in files:
        t = tag(f)
        for m, _, _ in METHODS:
            if (t, m) in done:
                continue
            p = os.path.join(RES, f"{t}.{m}.bin")
            if os.path.exists(p):
                print(f"[driver] FATAL: collision {p}", flush=True)
                sys.exit(1)
    print("[driver] no .bin collisions", flush=True)

    row = 0
    for n, fpath in enumerate(files, 1):
        t = tag(fpath)
        orig = os.path.getsize(fpath)
        for method, encf, decf in METHODS:
            if (t, method) in done:
                continue
            out_bin = os.path.join(RES, f"{t}.{method}.bin")
            dec_tmp = f"/tmp/arsenal-{os.getpid()}-{n}-{method}.dec"
            note = ""
            comp = ""
            ratio = ""
            enc_s = 0.0
            dec_s = 0.0
            sha = ""
            rc, enc_s, so, se = run_encode(encf(fpath, out_bin), out_bin)
            if rc == "TIMEOUT":
                note = "killed -- no output/CPU progress for >1200s"
                print(f"[{n}/76] {t} {method}: KILLED (stall >1200s)", flush=True)
            elif rc != 0:
                note = f"encode rc={rc}: {tail_err(se)}"
                if os.path.exists(out_bin):
                    try: os.remove(out_bin)
                    except OSError: pass
                print(f"[{n}/76] {t} {method}: encode failed rc={rc}", flush=True)
            else:
                comp = str(os.path.getsize(out_bin))
                ratio = f"{int(comp) / orig:.6f}" if orig else "0"
                rc2, dec_s, so2, se2 = run(decf(out_bin, fpath, dec_tmp), WATCHDOG_S)
                if rc2 == "TIMEOUT":
                    note = "decode killed/hung -- no result"
                    sha = "FAIL"
                    print(f"[{n}/76] {t} {method}: decode KILLED", flush=True)
                elif rc2 != 0:
                    note = f"decode rc={rc2}: {tail_err(se2)}"
                    sha = "FAIL"
                    print(f"[{n}/76] {t} {method}: decode failed rc={rc2}", flush=True)
                else:
                    try:
                        if sha256(fpath) == sha256(dec_tmp):
                            sha = "OK"
                        else:
                            sha = "FAIL"
                            note = "SHA-256 mismatch"
                    except OSError as e:
                        sha = "FAIL"
                        note = f"sha error: {e}"
                if os.path.exists(dec_tmp):
                    try: os.remove(dec_tmp)
                    except OSError: pass
                if sha != "OK":
                    print(f"[{n}/76] {t} {method}: comp={comp} sha={sha} {note}", flush=True)
            fh.write("\t".join([t, method, str(orig), comp, ratio,
                                 f"{enc_s:.3f}", f"{dec_s:.3f}", sha, note]) + "\n")
            row += 1
            if row % 20 == 0:
                print(f"[driver] {row} rows written", flush=True)
    fh.close()
    print(f"[driver] DONE: {row} rows -> {OUT}", flush=True)

if __name__ == "__main__":
    main()
