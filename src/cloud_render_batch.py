"""
cloud_render_batch.py — Script Runner Matrix Paralel di GitHub Actions
Fitur:
- Menerima argumen --start dan --end (misal: worker 1 render 1-16, worker 2 render 17-32, dst).
- Merender klip adegan dengan:
  1. Ken Burns dinamis mengikuti durasi audio.
  2. Heavy Grunge Texture (Grayscale Screen Blend 35%).
  3. Vignette cembung CRT TV jadul.
  4. Watermark 'documentary by: BANYAK TAU' (clean no stroke, flush-left).
  5. Subtitle Poppins Bold (700) strict lowercase.
  6. Audio 48.000 Hz Stereo AAC.
"""
import os
import sys
import json
import argparse
import subprocess

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
FLOW_DIR = os.path.join(BASE_DIR, "output/flow_images")
AUDIO_DIR = os.path.join(BASE_DIR, "output/audio")
SUB_DIR = os.path.join(BASE_DIR, "output/subtitles")
OUT_CLIPS_DIR = os.path.join(BASE_DIR, "output/rendered_clips")
FONTS_DIR = os.path.join(BASE_DIR, "assets/fonts")
GRUNGE_MP4 = os.path.join(BASE_DIR, "assets/heavy-grunge-texture-background-camila-ballell.mp4")
WM_FILE = os.path.join(BASE_DIR, "assets/watermark_clean_no_stroke.png")

os.makedirs(OUT_CLIPS_DIR, exist_ok=True)

def render_single_shot(shot_id_num):
    shot_str = f"shot_{shot_id_num:03d}"
    img_p = os.path.join(FLOW_DIR, f"{shot_str}.png")
    audio_p = os.path.join(AUDIO_DIR, f"{shot_str}.mp3")
    sub_p = os.path.join(SUB_DIR, f"{shot_str}.srt")
    out_mp4 = os.path.join(OUT_CLIPS_DIR, f"{shot_str}.mp4")

    if not os.path.exists(img_p) or not os.path.exists(audio_p):
        print(f"Skipping {shot_str}, file not found.")
        return

    # Durasi audio
    cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_p]
    dur = float(subprocess.run(cmd_dur, capture_output=True, text=True).stdout.strip())
    total_frames = int(dur * 30)

    sub_rel = f"output/subtitles/{shot_str}.srt"
    sub_style = (
        f"subtitles='{sub_rel}':fontsdir='assets/fonts':force_style="
        f"'Fontname=Poppins Bold,Fontsize=17,PrimaryColour=&H00FFFFFF,OutlineColour=&H90050505,"
        f"BorderStyle=1,Outline=1.0,Shadow=1.6,MarginV=34,Alignment=2'"
    )

    zoom_step = 0.070 / float(total_frames)

    # Filter graph:
    # 0: Base image
    # 1: Heavy Grunge
    # 2: Audio MP3
    # 3: Watermark PNG
    filter_complex = (
        f"[0:v]scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,"
        f"zoompan=z='min(zoom+{zoom_step:.6f},1.070)':x='iw*0.50-(iw/zoom/2)':y='ih*0.48-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps=30,"
        f"format=rgb24[base];"
        f"[1:v]scale=1920:1080,format=gray,format=rgb24,colorchannelmixer=rr=0.35:gg=0.35:bb=0.35[grunge];"
        f"[base][grunge]blend=all_mode=screen,format=rgb24[blended];"
        f"[blended]vignette=PI/4.2:eval=init,format=yuv420p[vignetted];"
        f"[vignetted][3:v]overlay=(W-w)/2:835[with_wm];"
        f"[with_wm]{sub_style}[outv]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_p,
        "-stream_loop", "-1", "-i", GRUNGE_MP4,
        "-i", audio_p,
        "-i", WM_FILE,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "2:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
        "-t", f"{dur:.2f}",
        out_mp4
    ]

    subprocess.run(cmd, check=True, cwd=BASE_DIR)
    print(f"✓ Rendered {shot_str}.mp4 ({dur:.2f}s)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=77)
    args = parser.parse_args()

    print(f"=== CLOUD RENDER WORKER: Shots {args.start} to {args.end} ===")
    for shot_id in range(args.start, args.end + 1):
        render_single_shot(shot_id)
    print("=== WORKER BATCH COMPLETED ===")

if __name__ == "__main__":
    main()
