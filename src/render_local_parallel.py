"""
render_local_parallel.py — Render 77 klip secara paralel + assembly v3 (lokal).
Memakai 4 worker paralel untuk memanfaatkan CPU multi-core.
"""
import os
import sys
import subprocess
import concurrent.futures
import time

BASE = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(BASE, "src"))

PY = sys.executable
WORKERS = 4
TOTAL = 77


def run_batch(rng):
    start, end = rng
    t0 = time.time()
    r = subprocess.run(
        [PY, os.path.join(BASE, "src", "cloud_render_batch.py"), "--start", str(start), "--end", str(end)],
        cwd=BASE, capture_output=True, text=True
    )
    ok = r.returncode == 0
    print(f"[batch {start}-{end}] {'OK' if ok else 'FAIL'} in {time.time()-t0:.0f}s", flush=True)
    if not ok:
        print(r.stderr[-2000:], flush=True)
    return ok


def main():
    # bagi 77 shot ke WORKERS batch
    per = (TOTAL + WORKERS - 1) // WORKERS
    ranges = []
    s = 1
    while s <= TOTAL:
        e = min(s + per - 1, TOTAL)
        ranges.append((s, e))
        s = e + 1

    print(f"=== RENDER LOKAL PARALEL: {WORKERS} worker, batches {ranges} ===", flush=True)
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(run_batch, ranges))
    print(f"=== RENDER SELESAI dalam {(time.time()-t0)/60:.1f} menit, sukses={sum(results)}/{len(results)} ===", flush=True)

    if not all(results):
        print("Ada batch gagal, hentikan sebelum assembly.", flush=True)
        return 1

    # validasi jumlah klip
    clips_dir = os.path.join(BASE, "output/rendered_clips")
    n = len([f for f in os.listdir(clips_dir) if f.startswith("shot_") and f.endswith(".mp4")])
    print(f"Klip terender: {n}/{TOTAL}", flush=True)
    if n < TOTAL:
        print("Klip kurang, hentikan.", flush=True)
        return 1

    print("=== MULAI ASSEMBLY v3 ===", flush=True)
    t1 = time.time()
    r = subprocess.run([PY, os.path.join(BASE, "src", "cloud_assemble_master.py")],
                       cwd=BASE, capture_output=True, text=True)
    print(r.stdout[-4000:], flush=True)
    if r.returncode != 0:
        print("ASSEMBLY GAGAL:", flush=True)
        print(r.stderr[-4000:], flush=True)
        return 1
    print(f"=== ASSEMBLY SELESAI dalam {(time.time()-t1)/60:.1f} menit ===", flush=True)
    print(f"=== TOTAL WAKTU: {(time.time()-t0)/60:.1f} menit ===", flush=True)
    print("LOCAL_RENDER_ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
