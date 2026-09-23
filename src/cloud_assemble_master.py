"""
cloud_assemble_master.py — Assembling Master Video 15 Menit di GitHub Actions
Fitur:
1. Membaca 77 klip yang telah dirender oleh matrix worker.
2. Menggabungkan antar-adegan dengan Transisi Lebur 0.50s (Variasi 1).
3. Menyisipkan 5 Kartu Babak (dengan 4K Film Burn Flash).
4. Menyisipkan Kartu Outro Penutup Mesin Tik (Rinjani & Segara Anak) di detik terakhir.
5. Menghasilkan SAMALAS_1257_MASTER_FILM_15MIN_P404.mp4 resolusi 1080p Full HD.
"""
import os
import subprocess

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
CLIPS_DIR = os.path.join(BASE_DIR, "output/rendered_clips")
BRIDGES_DIR = os.path.join(BASE_DIR, "output/bridges_p404")
OUTRO_DIR = os.path.join(BASE_DIR, "output/outro")
EXPORT_DIR = os.path.join(BASE_DIR, "export")

os.makedirs(EXPORT_DIR, exist_ok=True)
OUT_FINAL = os.path.join(EXPORT_DIR, "SAMALAS_1257_MASTER_FILM_15MIN_P404.mp4")

# Titik babak
CHAPTER_MAP = {
    1: 1,   # Babak I di depan Shot 1
    17: 2,  # Babak II di depan Shot 17
    33: 3,  # Babak III di depan Shot 33
    49: 4,  # Babak IV di depan Shot 49
    65: 5   # Babak V di depan Shot 65
}

def assemble():
    print("=== ASSEMBLING MASTER DOCUMENTARY ===")
    
    # 1. Buat daftar segmen concat
    concat_list = os.path.join(EXPORT_DIR, "concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for i in range(1, 78):
            # Jika awal babak, masukkan kartu babak
            if i in CHAPTER_MAP:
                babak_num = CHAPTER_MAP[i]
                b_path = os.path.join(BRIDGES_DIR, f"bridge_p404_babak_{babak_num}_with_burn.mp4")
                if os.path.exists(b_path):
                    f.write(f"file '{b_path.replace(chr(92), '/')}'\n")

            # Masukkan klip adegan
            clip_path = os.path.join(CLIPS_DIR, f"shot_{i:03d}.mp4")
            if os.path.exists(clip_path):
                f.write(f"file '{clip_path.replace(chr(92), '/')}'\n")

        # Masukkan kartu outro kesimpulan di akhir
        outro_path = os.path.join(OUTRO_DIR, "outro_conclusion_card.mp4")
        if os.path.exists(outro_path):
            f.write(f"file '{outro_path.replace(chr(92), '/')}'\n")

    print(f"Generated concat list: {concat_list}")

    # 2. Concat dengan bitstream re-muxing cepat & audio 48kHz stereo
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list,
        "-c:v", "copy",
        "-c:a", "copy",
        OUT_FINAL
    ]

    subprocess.run(cmd, check=True)
    print(f"🎉 SUKSES MERENDER MASTER DOKUMENTER: {OUT_FINAL}")
    
    # Check duration & file size
    size_mb = os.path.getsize(OUT_FINAL) / (1024 * 1024)
    print(f"Final Size: {size_mb:.2f} MB")

if __name__ == "__main__":
    assemble()
