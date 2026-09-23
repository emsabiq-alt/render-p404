"""
cloud_assemble_master.py — Assembly Master Documentary dengan Crossfade 0.5s
Perbaikan v2:
1. Crossfade 0.5s (15 frame) antar-scene dalam babak yang sama.
2. Hard cut pada pergantian babak (bridge → shot pertama babak).
3. Bridge chapter + Outro tetap dimasukkan.
4. Menggunakan FFmpeg xfade filter chain.
"""
import os
import subprocess
import json

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
CLIPS_DIR = os.path.join(BASE_DIR, "output/rendered_clips")
BRIDGES_DIR = os.path.join(BASE_DIR, "output/bridges_p404")
OUTRO_DIR = os.path.join(BASE_DIR, "output/outro")
EXPORT_DIR = os.path.join(BASE_DIR, "export")

os.makedirs(EXPORT_DIR, exist_ok=True)
OUT_FINAL = os.path.join(EXPORT_DIR, "SAMALAS_1257_MASTER_FILM_15MIN_P404.mp4")

CHAPTER_MAP = {
    1: 1, 17: 2, 33: 3, 49: 4, 65: 5
}

XFADE_DUR = 0.5  # crossfade duration in seconds

def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())

def build_segment_groups():
    """
    Bangun grup segmen per babak.
    Setiap babak: [bridge, shot_X, shot_X+1, ..., shot_Y]
    Antar-shot dalam babak = crossfade.
    Antar-babak (bridge→shot) = hard cut (bridge sudah punya film burn).
    """
    groups = []  # list of lists
    chapter_starts = sorted(CHAPTER_MAP.keys())

    for idx, ch_start in enumerate(chapter_starts):
        ch_end = chapter_starts[idx + 1] - 1 if idx + 1 < len(chapter_starts) else 77
        babak_num = CHAPTER_MAP[ch_start]

        group = []
        # Bridge
        b_path = os.path.join(BRIDGES_DIR, f"bridge_p404_babak_{babak_num}_with_burn.mp4")
        if os.path.exists(b_path):
            group.append(("bridge", b_path))

        # Shots in this chapter
        for s in range(ch_start, ch_end + 1):
            clip = os.path.join(CLIPS_DIR, f"shot_{s:03d}.mp4")
            if os.path.exists(clip):
                group.append(("shot", clip))

        groups.append(group)

    # Outro
    outro = os.path.join(OUTRO_DIR, "outro_conclusion_card.mp4")
    if os.path.exists(outro):
        groups.append([("outro", outro)])

    return groups

def crossfade_group(group, group_idx, temp_dir):
    """
    Crossfade semua klip dalam satu grup (babak).
    Bridge→shot pertama: hard cut (no crossfade).
    shot→shot: crossfade 0.5s.
    """
    if len(group) == 0:
        return None
    if len(group) == 1:
        return group[0][1]

    # Pisahkan bridge dari shots
    segments = []
    for seg_type, seg_path in group:
        segments.append((seg_type, seg_path))

    # Strategi: concat bridge+shot1 tanpa crossfade, lalu crossfade shot1→shot2→...→shotN
    # Ambil semua shots saja untuk crossfade chain
    bridge_path = None
    shot_paths = []
    for seg_type, seg_path in segments:
        if seg_type == "bridge":
            bridge_path = seg_path
        else:
            shot_paths.append(seg_path)

    if len(shot_paths) == 0:
        return bridge_path

    # Crossfade chain antar shots menggunakan xfade
    if len(shot_paths) == 1:
        crossfaded_shots = shot_paths[0]
    else:
        # Build FFmpeg xfade filter chain
        n = len(shot_paths)
        inputs = []
        for p in shot_paths:
            inputs.extend(["-i", p])

        # Calculate offsets: setiap crossfade terjadi di (cumulative_duration - xfade_dur)
        durations = [get_duration(p) for p in shot_paths]

        # Build video xfade chain
        v_filters = []
        a_filters = []
        cumul = durations[0]

        for i in range(1, n):
            offset = cumul - XFADE_DUR
            if offset < 0:
                offset = 0

            in_v = f"[xv{i-1}]" if i > 1 else "[0:v]"
            in_a = f"[xa{i-1}]" if i > 1 else "[0:a]"
            out_v = f"[xv{i}]" if i < n - 1 else "[outv]"
            out_a = f"[xa{i}]" if i < n - 1 else "[outa]"

            v_filters.append(f"{in_v}[{i}:v]xfade=transition=fade:duration={XFADE_DUR}:offset={offset:.3f}{out_v}")
            a_filters.append(f"{in_a}[{i}:a]acrossfade=d={XFADE_DUR}:c1=tri:c2=tri{out_a}")

            cumul += durations[i] - XFADE_DUR

        filter_str = ";".join(v_filters + a_filters)

        crossfaded_out = os.path.join(temp_dir, f"group_{group_idx}_shots_xfade.mp4")
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            crossfaded_out
        ]
        subprocess.run(cmd, check=True)
        crossfaded_shots = crossfaded_out

    # Jika ada bridge, concat bridge + crossfaded_shots (hard cut)
    if bridge_path:
        concat_txt = os.path.join(temp_dir, f"group_{group_idx}_concat.txt")
        with open(concat_txt, "w") as f:
            f.write(f"file '{bridge_path.replace(chr(92), '/')}'\n")
            f.write(f"file '{crossfaded_shots.replace(chr(92), '/')}'\n")

        group_out = os.path.join(temp_dir, f"group_{group_idx}_final.mp4")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_txt,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            group_out
        ]
        subprocess.run(cmd, check=True)
        return group_out
    else:
        return crossfaded_shots

def assemble():
    print("=== ASSEMBLING MASTER DOCUMENTARY v2 (with crossfade) ===")

    temp_dir = os.path.join(EXPORT_DIR, "temp_assembly")
    os.makedirs(temp_dir, exist_ok=True)

    groups = build_segment_groups()
    print(f"Total segment groups (chapters + outro): {len(groups)}")

    # Process each group
    group_outputs = []
    for idx, group in enumerate(groups):
        print(f"\n--- Processing Group {idx + 1} ({len(group)} segments) ---")
        out = crossfade_group(group, idx, temp_dir)
        if out:
            group_outputs.append(out)
            dur = get_duration(out)
            print(f"  Group {idx + 1} output: {dur:.2f}s")

    # Final concat of all groups (hard cut between chapters)
    final_concat = os.path.join(temp_dir, "final_concat.txt")
    with open(final_concat, "w") as f:
        for p in group_outputs:
            f.write(f"file '{p.replace(chr(92), '/')}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", final_concat,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
        OUT_FINAL
    ]
    subprocess.run(cmd, check=True)

    size_mb = os.path.getsize(OUT_FINAL) / (1024 * 1024)
    dur = get_duration(OUT_FINAL)
    print(f"\n🎉 MASTER FILM SELESAI: {OUT_FINAL}")
    print(f"   Durasi: {dur:.2f}s ({dur/60:.1f} menit)")
    print(f"   Ukuran: {size_mb:.2f} MB")

    # Cleanup temp
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    assemble()
