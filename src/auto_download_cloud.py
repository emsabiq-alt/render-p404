"""Auto-download master artifact dari GitHub Actions render-p404.

Pakai:
  python src/auto_download_cloud.py --run 35836556928

Tugas:
  1. Poll run sampai selesai.
  2. Cari artifact yang namanya mengandung MASTER/SAMALAS.
  3. Download zip via gh api.
  4. Extract mp4.
  5. Copy ke export/SAMALAS_1257_MASTER_FILM_15MIN_P404_CLOUD.mp4.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

REPO = "emsabiq-alt/render-p404"
BASE = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
EXPORT = os.path.join(BASE, "export")
DL_DIR = os.path.join(EXPORT, "cloud_auto_download")
FINAL = os.path.join(EXPORT, "SAMALAS_1257_MASTER_FILM_15MIN_P404_CLOUD.mp4")
LOG = os.path.join(EXPORT, "cloud_auto_download.log")


def log(msg):
    line = time.strftime("[%H:%M:%S] ") + msg
    print(line, flush=True)
    os.makedirs(EXPORT, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, *, text=True, timeout=120):
    r = subprocess.run(cmd, capture_output=True, text=text, timeout=timeout)
    if r.returncode != 0:
        err = r.stderr if text else r.stderr.decode("utf-8", "ignore")
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{err}")
    return r.stdout


def gh_json(args):
    return json.loads(run(["gh", *args]))


def run_status(run_id):
    return gh_json(["run", "view", str(run_id), "-R", REPO, "--json", "status,conclusion,url"])


def artifacts(run_id):
    return gh_json(["api", f"repos/{REPO}/actions/runs/{run_id}/artifacts"])["artifacts"]


def pick_artifact(items):
    usable = [a for a in items if not a.get("expired")]
    masters = [a for a in usable if any(k in a["name"].upper() for k in ("MASTER", "SAMALAS", "FILM"))]
    return (masters or usable)[0] if usable else None


def download_zip(artifact_id, out_zip):
    with open(out_zip, "wb") as f:
        p = subprocess.run(
            ["gh", "api", f"repos/{REPO}/actions/artifacts/{artifact_id}/zip"],
            stdout=f, stderr=subprocess.PIPE, text=False, timeout=1800,
        )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "ignore"))
    if os.path.getsize(out_zip) < 1024:
        raise RuntimeError(f"zip terlalu kecil: {out_zip}")


def extract_first_mp4(zpath, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".mp4")]
        if not names:
            raise RuntimeError("artifact tidak berisi mp4")
        # pilih file terbesar
        names.sort(key=lambda n: z.getinfo(n).file_size, reverse=True)
        name = names[0]
        out = os.path.join(dest_dir, os.path.basename(name))
        with z.open(name) as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst)
        return out


def self_check():
    fake = [
        {"name": "chunks", "expired": False},
        {"name": "SAMALAS_1257_MASTER_FILM_15MIN_P404", "expired": False},
    ]
    assert pick_artifact(fake)["name"].startswith("SAMALAS")
    assert pick_artifact([{"name": "x", "expired": True}]) is None
    print("auto_download self-check: 2 assertions passed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="GitHub Actions run id")
    ap.add_argument("--interval", type=int, default=60)
    args = ap.parse_args()

    self_check()
    os.makedirs(DL_DIR, exist_ok=True)
    log(f"watch run {args.run}: https://github.com/{REPO}/actions/runs/{args.run}")

    while True:
        st = run_status(args.run)
        log(f"status={st['status']} conclusion={st.get('conclusion')}")
        if st["status"] == "completed":
            if st.get("conclusion") != "success":
                raise SystemExit(f"run selesai tapi gagal: {st.get('conclusion')}")
            break
        time.sleep(args.interval)

    items = artifacts(args.run)
    art = pick_artifact(items)
    if not art:
        raise SystemExit("tidak ada artifact yang bisa diunduh")

    log(f"artifact={art['name']} id={art['id']} size={art.get('size_in_bytes')}")
    zpath = os.path.join(DL_DIR, f"artifact_{art['id']}.zip")
    download_zip(art["id"], zpath)
    log(f"downloaded zip {os.path.getsize(zpath)} bytes")

    mp4 = extract_first_mp4(zpath, DL_DIR)
    shutil.copy2(mp4, FINAL)
    log(f"FINAL_READY {FINAL} ({os.path.getsize(FINAL)} bytes)")


if __name__ == "__main__":
    main()
