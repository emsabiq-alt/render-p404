"""
dashboard.py — Dashboard render lokal Project 404 (Samalas 1257).
Server HTTP stdlib, tanpa dependensi.

Fitur:
  - progres render 77 klip + tahap assembly
  - grid 77 shot dengan status per-scene
  - inspektur scene: naskah TTS, subtitle, VO, klip
  - QA otomatis: deteksi angka mentah, subtitle 2 baris, klip rusak, VO hilang
  - pemutar audio VO per-scene & pratinjau MP4 (range-seek)
  - ETA berbasis kecepatan render nyata
  - status GitHub Actions
Jalankan:  python src/dashboard.py   ->  http://127.0.0.1:5188/
"""
import contextlib
import json
import os
import re
import subprocess
import time
import wave
import uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote, parse_qs

BASE = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
CLIPS = os.path.join(BASE, "output/rendered_clips")
AUDIO = os.path.join(BASE, "output/audio_supertonic")
SUBS = os.path.join(BASE, "output/subtitles")
EXPORT = os.path.join(BASE, "export")
SCRIPT = os.path.join(BASE, "script")
STORY = os.path.join(BASE, "input/samalas_master_storyboard_enriched.json")
LOG = os.path.join(EXPORT, "local_render_m2.log")
HTML = os.path.join(BASE, "dashboard.html")
THUMB_DIR = os.path.join(EXPORT, "thumbnail_flow")

TOTAL_SHOTS = 77
PORT = 5188
REPO = "emsabiq-alt/render-p404"
CHAPTER_STARTS = {1: 1, 17: 2, 33: 3, 49: 4, 65: 5}

_gh_cache = {"at": 0.0, "data": None}
_GH_TTL = 20.0
_scene_cache = {"at": 0.0, "data": None}
_SCENE_TTL = 4.0
_start_time = time.time()


# ── util ────────────────────────────────────────────────────────
def wav_duration(path):
    try:
        with contextlib.closing(wave.open(path, "rb")) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


def count_files(d, suffix):
    if not os.path.isdir(d):
        return 0
    return len([f for f in os.listdir(d) if f.endswith(suffix)])


def read_log_tail(n=40):
    if not os.path.exists(LOG):
        return []
    try:
        with open(LOG, encoding="utf-8", errors="ignore") as f:
            return [l.rstrip("\n\r") for l in f if l.strip()][-n:]
    except Exception:
        return []


def phase_from_log(lines, clips_done):
    joined = "\n".join(lines)
    if "LOCAL_RENDER_ALL_DONE" in joined:
        return "selesai", "Render dan assembly selesai"
    if "ASSEMBLY GAGAL" in joined or "] FAIL" in joined:
        return "gagal", "Ada tahap yang gagal - periksa log"
    if "MULAI ASSEMBLY" in joined:
        return "assembly", "Menggabungkan klip: crossfade, musik, ketikan"
    if clips_done > 0:
        return "render", f"Merender klip {clips_done}/{TOTAL_SHOTS}"
    if joined:
        return "mulai", "Menyiapkan worker render"
    return "idle", "Belum ada proses berjalan"


def chapter_of(n):
    ch = 1
    for start, c in sorted(CHAPTER_STARTS.items()):
        if n >= start:
            ch = c
    return ch


def eta_seconds(clips_done):
    """ETA dari kecepatan nyata sejak server hidup; None kalau belum cukup data."""
    if clips_done <= 0 or clips_done >= TOTAL_SHOTS:
        return None
    elapsed = time.time() - _start_time
    if elapsed < 30:
        return None
    rate = clips_done / elapsed
    if rate <= 0:
        return None
    return int((TOTAL_SHOTS - clips_done) / rate)


# ── Video Factory ───────────────────────────────────────────────
def validate_video_request(data):
    title = (data.get("title") or "").strip()
    topic = (data.get("topic") or "").strip()
    if not title:
        return False, "Judul video wajib diisi"
    if not topic:
        return False, "Topik/ringkasan cerita wajib diisi"
    if len(title) > 140:
        return False, "Judul terlalu panjang"
    return True, ""


def next_project_dir(projects_root=Path("D:/project")):
    root = Path(projects_root)
    root.mkdir(parents=True, exist_ok=True)
    nums = []
    for p in root.iterdir():
        if p.is_dir() and re.fullmatch(r"a\d{3}", p.name):
            nums.append(int(p.name[1:]))
    return root / f"a{(max(nums) + 1 if nums else 1):03d}"


def create_video_job(data, projects_root=Path("D:/project")):
    ok, err = validate_video_request(data)
    if not ok:
        raise ValueError(err)

    project = next_project_dir(projects_root)
    project.mkdir(parents=True, exist_ok=False)
    job_id = time.strftime("vf_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    pipeline = [
        {"key": "outline", "label": "Outline", "status": "pending"},
        {"key": "script", "label": "Script", "status": "waiting"},
        {"key": "storyboard", "label": "Storyboard", "status": "waiting"},
        {"key": "assets", "label": "Visual Assets", "status": "waiting"},
        {"key": "tts", "label": "TTS + Subtitle", "status": "waiting"},
        {"key": "render", "label": "Local + Cloud Render", "status": "waiting"},
    ]
    cfg = {
        "job_id": job_id,
        "title": data["title"].strip(),
        "topic": data["topic"].strip(),
        "style": data.get("style") or "project404",
        "duration": data.get("duration") or "8-12 menit",
        "voice": data.get("voice") or "M2",
        "mode": data.get("mode") or "step",
        "output": data.get("output") or "local+cloud",
        "status": "created",
        "project_dir": str(project).replace("\\", "/"),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pipeline": pipeline,
    }
    (project / "project.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    (project / "factory.log").write_text(
        f"[{cfg['created_at']}] created {job_id}\n"
        f"title: {cfg['title']}\nstyle: {cfg['style']}\nmode: {cfg['mode']}\n",
        encoding="utf-8",
    )
    return cfg


def recent_video_jobs(projects_root=Path("D:/project"), limit=10):
    jobs = []
    root = Path(projects_root)
    if root.exists():
        for p in root.glob("a[0-9][0-9][0-9]/project.json"):
            try:
                jobs.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jobs[:limit]


# ── Thumbnail Studio ────────────────────────────────────────────
def thumbnail_pack():
    meta = Path(THUMB_DIR) / "thumbnail_flow_pack.json"
    if not meta.exists():
        return {
            "method": "Google Flow via CDP/MCP flow automation; waiting for generation",
            "titles": [], "thumbnails": [], "description": "", "chapters": [], "music_credit": [],
            "metadata_path": str(meta).replace("\\", "/"),
        }
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["metadata_path"] = str(meta).replace("\\", "/")
    return data


def regenerate_thumbnail_pack():
    from flow_thumbnail_generator import generate_all
    return generate_all()


# ── data per-scene ──────────────────────────────────────────────
def load_narrations():
    out = {}
    try:
        with open(STORY, encoding="utf-8") as f:
            for s in json.load(f)["shots"]:
                out[s["id"]] = s.get("narration", "")
    except Exception:
        pass
    return out


def parse_srt(path):
    """Kembalikan list {start,end,text} dari file SRT."""
    items = []
    try:
        raw = open(path, encoding="utf-8").read().strip()
    except Exception:
        return items
    for block in re.split(r"\n\s*\n", raw):
        lines = [l for l in block.strip().split("\n") if l.strip()]
        if len(lines) < 3:
            continue
        m = re.match(r"([\d:,]+)\s*-->\s*([\d:,]+)", lines[1])
        if not m:
            continue
        items.append({"start": m.group(1), "end": m.group(2),
                      "text": " ".join(lines[2:]), "lines": len(lines) - 2})
    return items


def scene_rows():
    """Status ringkas 77 scene (di-cache singkat)."""
    now = time.time()
    if _scene_cache["data"] is not None and now - _scene_cache["at"] < _SCENE_TTL:
        return _scene_cache["data"]

    rows = []
    for i in range(1, TOTAL_SHOTS + 1):
        sid = f"shot_{i:03d}"
        wav = os.path.join(AUDIO, sid + ".wav")
        srt = os.path.join(SUBS, sid + ".srt")
        mp4 = os.path.join(CLIPS, sid + ".mp4")
        txt = os.path.join(SCRIPT, sid + ".txt")
        has_clip = os.path.isfile(mp4)
        size = os.path.getsize(mp4) if has_clip else 0
        rows.append({
            "n": i, "id": sid, "chapter": chapter_of(i),
            "vo": os.path.isfile(wav),
            "sub": os.path.isfile(srt),
            "script": os.path.isfile(txt),
            "clip": has_clip,
            "clip_mb": round(size / 1048576, 1) if has_clip else 0,
            "dur": round(wav_duration(wav), 1) if os.path.isfile(wav) else 0,
            "chapter_head": i in CHAPTER_STARTS,
        })
    _scene_cache["at"] = now
    _scene_cache["data"] = rows
    return rows


def scene_detail(n):
    sid = f"shot_{n:03d}"
    wav = os.path.join(AUDIO, sid + ".wav")
    srt = os.path.join(SUBS, sid + ".srt")
    mp4 = os.path.join(CLIPS, sid + ".mp4")
    txt = os.path.join(SCRIPT, sid + ".txt")
    narr = load_narrations().get(sid, "")
    script_text = ""
    if os.path.isfile(txt):
        script_text = open(txt, encoding="utf-8").read().strip()
    return {
        "n": n, "id": sid, "chapter": chapter_of(n),
        "narration": narr,
        "script": script_text,
        "subtitles": parse_srt(srt),
        "vo_dur": round(wav_duration(wav), 2) if os.path.isfile(wav) else 0,
        "has_vo": os.path.isfile(wav),
        "has_clip": os.path.isfile(mp4),
        "clip_mb": round(os.path.getsize(mp4) / 1048576, 1) if os.path.isfile(mp4) else 0,
    }


# ── QA otomatis ─────────────────────────────────────────────────
def run_qa():
    """Periksa masalah yang pernah terjadi di proyek ini."""
    issues = []

    # 1. angka mentah di script TTS (penyebab "1883" dibaca kacau)
    bad_num = []
    if os.path.isdir(SCRIPT):
        for i in range(1, TOTAL_SHOTS + 1):
            p = os.path.join(SCRIPT, f"shot_{i:03d}.txt")
            if not os.path.isfile(p):
                continue
            t = open(p, encoding="utf-8").read()
            if any(c.isdigit() for c in t):
                bad_num.append(i)
    issues.append({
        "key": "angka", "label": "Angka mentah di naskah TTS",
        "ok": not bad_num, "count": len(bad_num), "shots": bad_num[:12],
        "hint": "Angka harus dieja (1257 → seribu dua ratus lima puluh tujuh)",
    })

    # 2. em-dash yang bisa terbaca sebagai simbol
    bad_dash = []
    if os.path.isdir(SCRIPT):
        for i in range(1, TOTAL_SHOTS + 1):
            p = os.path.join(SCRIPT, f"shot_{i:03d}.txt")
            if os.path.isfile(p) and "\u2014" in open(p, encoding="utf-8").read():
                bad_dash.append(i)
    issues.append({
        "key": "dash", "label": "Em-dash di naskah TTS",
        "ok": not bad_dash, "count": len(bad_dash), "shots": bad_dash[:12],
        "hint": "Em-dash harus jadi koma agar dibaca sebagai jeda",
    })

    # 3. subtitle lebih dari satu baris
    multi = []
    if os.path.isdir(SUBS):
        for i in range(1, TOTAL_SHOTS + 1):
            p = os.path.join(SUBS, f"shot_{i:03d}.srt")
            if not os.path.isfile(p):
                continue
            if any(it["lines"] > 1 for it in parse_srt(p)):
                multi.append(i)
    issues.append({
        "key": "sub2", "label": "Subtitle lebih dari 1 baris",
        "ok": not multi, "count": len(multi), "shots": multi[:12],
        "hint": "Setiap subtitle harus satu baris, maksimal 6 kata",
    })

    # 4. subtitle melewati durasi VO (desync)
    over = []
    for i in range(1, TOTAL_SHOTS + 1):
        srt = os.path.join(SUBS, f"shot_{i:03d}.srt")
        wav = os.path.join(AUDIO, f"shot_{i:03d}.wav")
        if not (os.path.isfile(srt) and os.path.isfile(wav)):
            continue
        items = parse_srt(srt)
        if not items:
            continue
        end = items[-1]["end"]
        m = re.match(r"(\d+):(\d+):(\d+),(\d+)", end)
        if not m:
            continue
        secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
        if secs > wav_duration(wav) + 0.25:
            over.append(i)
    issues.append({
        "key": "desync", "label": "Subtitle melewati durasi VO",
        "ok": not over, "count": len(over), "shots": over[:12],
        "hint": "Subtitle harus berakhir sebelum narasi habis",
    })

    # 5. klip mencurigakan kecil (indikasi render gagal)
    tiny = []
    if os.path.isdir(CLIPS):
        for i in range(1, TOTAL_SHOTS + 1):
            p = os.path.join(CLIPS, f"shot_{i:03d}.mp4")
            if os.path.isfile(p) and os.path.getsize(p) < 512 * 1024:
                tiny.append(i)
    issues.append({
        "key": "tiny", "label": "Klip rusak / terlalu kecil",
        "ok": not tiny, "count": len(tiny), "shots": tiny[:12],
        "hint": "Klip < 0,5 MB kemungkinan gagal render",
    })

    # 6. aset wajib
    need = {
        "musik utama": os.path.join(BASE, "assets/music/bg_main_dark_cinematic.mp3"),
        "musik viking": os.path.join(BASE, "assets/music/bg_viking_chapter.mp3"),
        "suara ketikan": os.path.join(BASE, "assets/sfx/typewriter_burst.wav"),
        "watermark": os.path.join(BASE, "assets/watermark_clean_no_stroke.png"),
        "font Poppins": os.path.join(BASE, "assets/fonts/Poppins-Bold.ttf"),
    }
    missing = [k for k, p in need.items() if not os.path.isfile(p)]
    issues.append({
        "key": "assets", "label": "Aset produksi",
        "ok": not missing, "count": len(missing), "shots": [],
        "hint": "Kurang: " + ", ".join(missing) if missing else "Semua aset tersedia",
    })

    return issues


# ── GitHub ──────────────────────────────────────────────────────
def gh_runs():
    now = time.time()
    if _gh_cache["data"] is not None and now - _gh_cache["at"] < _GH_TTL:
        return _gh_cache["data"]
    out = []
    try:
        r = subprocess.run(
            ["gh", "run", "list", "-R", REPO, "--limit", "5",
             "--json", "databaseId,status,conclusion,displayTitle,workflowName,createdAt"],
            capture_output=True, text=True, timeout=25)
        if r.returncode == 0 and r.stdout.strip():
            for it in json.loads(r.stdout):
                out.append({
                    "id": it.get("databaseId"),
                    "status": it.get("status"),
                    "conclusion": it.get("conclusion") or "",
                    "title": (it.get("displayTitle") or "")[:70],
                    "workflow": it.get("workflowName") or "",
                    "created": it.get("createdAt") or "",
                    "url": f"https://github.com/{REPO}/actions/runs/{it.get('databaseId')}",
                })
    except Exception:
        pass
    _gh_cache["at"] = now
    _gh_cache["data"] = out
    return out


def list_videos():
    vids = []
    if os.path.isdir(EXPORT):
        for f in sorted(os.listdir(EXPORT)):
            if f.endswith(".mp4"):
                p = os.path.join(EXPORT, f)
                vids.append({"name": f,
                             "size_mb": round(os.path.getsize(p) / 1048576, 1),
                             "mtime": os.path.getmtime(p)})
    vids.sort(key=lambda v: -v["mtime"])
    return vids


def build_state():
    clips = count_files(CLIPS, ".mp4")
    vo = count_files(AUDIO, ".wav")
    subs = count_files(SUBS, ".srt")
    log = read_log_tail()
    phase, phase_text = phase_from_log(log, clips)

    vo_total = 0.0
    if os.path.isdir(AUDIO):
        for f in os.listdir(AUDIO):
            if f.endswith(".wav"):
                vo_total += wav_duration(os.path.join(AUDIO, f))

    batches = []
    for line in log:
        m = re.match(r"\[batch (\d+)-(\d+)\] (\w+) in (\d+)s", line)
        if m:
            batches.append({"range": f"{m.group(1)}-{m.group(2)}",
                            "ok": m.group(3) == "OK", "secs": int(m.group(4))})

    qa = run_qa()
    return {
        "phase": phase, "phase_text": phase_text,
        "clips": clips, "clips_total": TOTAL_SHOTS,
        "vo": vo, "subs": subs,
        "vo_minutes": round(vo_total / 60, 1),
        "eta": eta_seconds(clips),
        "batches": batches,
        "log": log[-14:],
        "gh": gh_runs(),
        "videos": list_videos(),
        "video_jobs": recent_video_jobs(),
        "thumbnail_pack": thumbnail_pack(),
        "scenes": scene_rows(),
        "qa": qa,
        "qa_ok": sum(1 for q in qa if q["ok"]),
        "qa_total": len(qa),
        "now": time.strftime("%H:%M:%S"),
    }


# ── HTTP ────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_media(self, folder, name, mime, exts):
        safe = os.path.basename(unquote(name))
        if not safe.endswith(exts):
            self.send_error(404)
            return
        path = os.path.join(folder, safe)
        if not os.path.isfile(path):
            self.send_error(404)
            return
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        start, end, code = 0, size - 1, 200
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2))
                end = min(end, size - 1)
                start = min(start, end)
                code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        remaining = length
        with open(path, "rb") as f:
            f.seek(start)
            while remaining > 0:
                chunk = f.read(min(262144, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionAbortedError):
                    return
                remaining -= len(chunk)

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)

        if p in ("/", "/dashboard.html"):
            try:
                body = open(HTML, "rb").read()
            except FileNotFoundError:
                self.send_error(404, "dashboard.html tidak ditemukan")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if p == "/api/state":
            self._json(build_state())
            return

        if p == "/api/scene":
            try:
                n = int(q.get("n", ["1"])[0])
            except ValueError:
                n = 1
            n = max(1, min(TOTAL_SHOTS, n))
            self._json(scene_detail(n))
            return

        if p == "/api/qa":
            self._json({"qa": run_qa()})
            return

        if p == "/api/video-jobs":
            self._json({"jobs": recent_video_jobs()})
            return

        if p == "/api/thumbnails":
            self._json(thumbnail_pack())
            return

        if p.startswith("/thumbnail/"):
            self._serve_media(THUMB_DIR, p[len("/thumbnail/"):], "image/png", (".png",))
            return

        if p.startswith("/video/"):
            self._serve_media(EXPORT, p[len("/video/"):], "video/mp4", (".mp4",))
            return

        if p.startswith("/clip/"):
            self._serve_media(CLIPS, p[len("/clip/"):], "video/mp4", (".mp4",))
            return

        if p.startswith("/vo/"):
            self._serve_media(AUDIO, p[len("/vo/"):], "audio/wav", (".wav",))
            return

        if p == "/api/open-folder":
            target = q.get("d", ["export"])[0]
            folder = {"export": EXPORT, "clips": CLIPS, "audio": AUDIO, "subs": SUBS}.get(target, EXPORT)
            try:
                os.startfile(folder)  # noqa: S606
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return

        self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/video-jobs":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                job = create_video_job(data)
                self._json({"ok": True, "job": job}, 201)
            except ValueError as e:
                self._json({"ok": False, "error": str(e)}, 400)
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p == "/api/thumbnails/regenerate":
            try:
                self._json({"ok": True, "pack": regenerate_thumbnail_pack()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        self.send_error(404)


def self_check():
    assert phase_from_log([], 0)[0] == "idle"
    assert phase_from_log(["=== RENDER LOKAL PARALEL: 4 worker"], 5)[0] == "render"
    assert phase_from_log(["=== MULAI ASSEMBLY v3 ==="], 77)[0] == "assembly"
    assert phase_from_log(["LOCAL_RENDER_ALL_DONE"], 77)[0] == "selesai"

    m = re.match(r"bytes=(\d*)-(\d*)", "bytes=100-199")
    assert m and m.group(1) == "100" and m.group(2) == "199"
    m2 = re.match(r"bytes=(\d*)-(\d*)", "bytes=500-")
    assert m2 and m2.group(1) == "500" and m2.group(2) == ""

    bm = re.match(r"\[batch (\d+)-(\d+)\] (\w+) in (\d+)s", "[batch 1-20] OK in 1494s")
    assert bm and bm.group(1) == "1" and bm.group(4) == "1494"

    # pemetaan bab
    assert chapter_of(1) == 1 and chapter_of(16) == 1
    assert chapter_of(17) == 2 and chapter_of(32) == 2
    assert chapter_of(65) == 5 and chapter_of(77) == 5

    # ETA aman saat data belum cukup
    assert eta_seconds(0) is None
    assert eta_seconds(TOTAL_SHOTS) is None

    print("dashboard self-check: 12 assertions passed")


if __name__ == "__main__":
    self_check()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Dashboard render: http://127.0.0.1:{PORT}/")
    print("Ctrl+C untuk berhenti.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard dihentikan.")
