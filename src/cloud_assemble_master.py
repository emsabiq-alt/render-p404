"""
cloud_assemble_master.py — Assembly v3
1. Crossfade 0.5s antar-scene dalam babak; hard-cut di pergantian babak.
2. Suara ketikan mesin tik dibakar ke tiap kartu babak.
3. Backsong utama (dark cinematic) loop sepanjang film, di-duck di bawah narasi.
4. Musik viking (brass) menyala saat kartu babak; backsong utama TETAP jalan.
5. Output 1080p H.264 + AAC 48kHz stereo.
"""
import os
import subprocess

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
CLIPS_DIR = os.path.join(BASE_DIR, "output/rendered_clips")
BRIDGES_DIR = os.path.join(BASE_DIR, "output/bridges_p404")
OUTRO_DIR = os.path.join(BASE_DIR, "output/outro")
EXPORT_DIR = os.path.join(BASE_DIR, "export")
MUSIC_DIR = os.path.join(BASE_DIR, "assets/music")
SFX_DIR = os.path.join(BASE_DIR, "assets/sfx")

BG_MAIN = os.path.join(MUSIC_DIR, "bg_main_dark_cinematic.mp3")
BG_VIKING = os.path.join(MUSIC_DIR, "bg_viking_chapter.mp3")
TYPE_BURST = os.path.join(SFX_DIR, "typewriter_burst.wav")

os.makedirs(EXPORT_DIR, exist_ok=True)
OUT_FINAL = os.path.join(EXPORT_DIR, "SAMALAS_1257_MASTER_FILM_15MIN_P404.mp4")

CHAPTER_MAP = {1: 1, 17: 2, 33: 3, 49: 4, 65: 5}
XFADE_DUR = 0.5

BG_MAIN_VOL = 0.16
BG_VIKING_VOL = 0.32
VIKING_LEN = 12.0
VIKING_FADE = 2.0


def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())


def bake_typewriter_bridge(bridge_path, out_path):
    """Mix suara ketikan mesin tik ke kartu babak."""
    fc = ("[1:a]adelay=150|150,volume=0.85[type];"
          "[0:a][type]amix=inputs=2:normalize=0:duration=first[a]")
    cmd = ["ffmpeg", "-y", "-i", bridge_path, "-i", TYPE_BURST,
           "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
           "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
           out_path]
    subprocess.run(cmd, check=True, capture_output=True)


def build_segment_groups(temp_dir):
    groups = []
    chapter_starts = sorted(CHAPTER_MAP.keys())
    for idx, ch_start in enumerate(chapter_starts):
        ch_end = chapter_starts[idx + 1] - 1 if idx + 1 < len(chapter_starts) else 77
        babak_num = CHAPTER_MAP[ch_start]
        group = []
        b_src = os.path.join(BRIDGES_DIR, f"bridge_p404_babak_{babak_num}_with_burn.mp4")
        if os.path.exists(b_src):
            b_typed = os.path.join(temp_dir, f"bridge_{babak_num}_typed.mp4")
            bake_typewriter_bridge(b_src, b_typed)
            group.append(("bridge", b_typed))
        for s in range(ch_start, ch_end + 1):
            clip = os.path.join(CLIPS_DIR, f"shot_{s:03d}.mp4")
            if os.path.exists(clip):
                group.append(("shot", clip))
        groups.append(group)
    outro = os.path.join(OUTRO_DIR, "outro_conclusion_card.mp4")
    if os.path.exists(outro):
        groups.append([("outro", outro)])
    return groups


def crossfade_shots(shot_paths, out_path):
    if not shot_paths:
        return None
    if len(shot_paths) == 1:
        return shot_paths[0]
    n = len(shot_paths)
    durations = [get_duration(p) for p in shot_paths]
    inputs = []
    for p in shot_paths:
        inputs.extend(["-i", p])
    v_filters, a_filters = [], []
    cumul = durations[0]
    for i in range(1, n):
        offset = max(cumul - XFADE_DUR, 0)
        in_v = f"[xv{i-1}]" if i > 1 else "[0:v]"
        in_a = f"[xa{i-1}]" if i > 1 else "[0:a]"
        out_v = f"[xv{i}]" if i < n - 1 else "[outv]"
        out_a = f"[xa{i}]" if i < n - 1 else "[outa]"
        v_filters.append(f"{in_v}[{i}:v]xfade=transition=fade:duration={XFADE_DUR}:offset={offset:.3f}{out_v}")
        a_filters.append(f"{in_a}[{i}:a]acrossfade=d={XFADE_DUR}:c1=tri:c2=tri{out_a}")
        cumul += durations[i] - XFADE_DUR
    fc = ";".join(v_filters + a_filters)
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", fc, "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def concat_hardcut(paths, out_path, temp_dir):
    txt = os.path.join(temp_dir, "concat_" + os.path.basename(out_path) + ".txt")
    with open(txt, "w") as f:
        for p in paths:
            ap = os.path.abspath(p).replace(chr(92), '/')
            f.write(f"file '{ap}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", txt,
           "-c:v", "libx264", "-preset", "fast", "-crf", "18",
           "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def mix_music(video_narration, chapter_offsets, out_path):
    total = get_duration(video_narration)
    inputs = ["-i", video_narration, "-stream_loop", "-1", "-i", BG_MAIN]
    viking_idx = []
    for _ in chapter_offsets:
        inputs.extend(["-i", BG_VIKING])
        viking_idx.append(len(viking_idx) + 2)

    parts = ["[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[narr][narrsc]",
             f"[1:a]atrim=0:{total:.3f},volume={BG_MAIN_VOL},"
             f"aformat=sample_rates=48000:channel_layouts=stereo[bgmain]"]
    vk_labels = []
    for k, (off, idx) in enumerate(zip(chapter_offsets, viking_idx)):
        parts.append(
            f"[{idx}:a]atrim=0:{VIKING_LEN},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={VIKING_FADE},afade=t=out:st={VIKING_LEN-VIKING_FADE}:d={VIKING_FADE},"
            f"volume={BG_VIKING_VOL},aformat=sample_rates=48000:channel_layouts=stereo,"
            f"adelay={int(off*1000)}|{int(off*1000)}[vk{k}]")
        vk_labels.append(f"[vk{k}]")
    music_ins = "[bgmain]" + "".join(vk_labels)
    parts.append(f"{music_ins}amix=inputs={1+len(vk_labels)}:normalize=0:duration=first[music]")
    parts.append("[music][narrsc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[ducked]")
    parts.append("[narr][ducked]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.97[aout]")

    fc = ";".join(parts)
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
        "-shortest", out_path]
    subprocess.run(cmd, check=True)
    return out_path


def assemble():
    print("=== ASSEMBLING MASTER v3 (crossfade + typewriter + backsong + viking) ===")
    temp_dir = os.path.join(EXPORT_DIR, "temp_assembly")
    os.makedirs(temp_dir, exist_ok=True)

    groups = build_segment_groups(temp_dir)
    print(f"Segment groups: {len(groups)}")

    group_outputs, chapter_offsets = [], []
    running = 0.0
    for idx, group in enumerate(groups):
        bridge = [p for t, p in group if t == "bridge"]
        shots = [p for t, p in group if t == "shot"]
        outro = [p for t, p in group if t == "outro"]
        if outro:
            group_out = outro[0]
        else:
            xf = crossfade_shots(shots, os.path.join(temp_dir, f"g{idx}_shots.mp4"))
            if bridge and xf:
                chapter_offsets.append(running)
                group_out = concat_hardcut([bridge[0], xf],
                                           os.path.join(temp_dir, f"g{idx}_final.mp4"), temp_dir)
            elif bridge:
                chapter_offsets.append(running)
                group_out = bridge[0]
            else:
                group_out = xf
        d = get_duration(group_out)
        running += d
        group_outputs.append(group_out)
        print(f"  Group {idx+1}: {d:.2f}s (running {running:.2f}s)")

    narration_master = concat_hardcut(group_outputs,
                                      os.path.join(temp_dir, "narration_master.mp4"), temp_dir)
    print(f"Narration master: {get_duration(narration_master):.2f}s")
    print(f"Chapter offsets: {[round(o,1) for o in chapter_offsets]}")

    print("Mixing backsong + viking + duck...")
    mix_music(narration_master, chapter_offsets, OUT_FINAL)

    dur = get_duration(OUT_FINAL)
    size_mb = os.path.getsize(OUT_FINAL) / (1024 * 1024)
    print(f"\nMASTER v3 SELESAI: {OUT_FINAL}")
    print(f"   Durasi: {dur:.2f}s ({dur/60:.1f} menit) | {size_mb:.1f} MB")

    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    assemble()
