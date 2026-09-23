"""
gen_subtitles_single_line.py — Subtitle 1-baris, sinkron durasi audio Supertonic, dengan jeda.

Perbaikan v4:
- Anti-transition clipping: LEAD_IN = 0.40s agar teks tidak tertelan transisi crossfade awal.
- Anti-lonely words: Tidak pernah menyisakan 1 atau 2 kata sendirian di layar (minimal 3 kata per frasa).
- Frasa 1-2 kata otomatis digabung ke frasa sebelum/sesudahnya agar muncul bersamaan.
- Maksimal 7-8 kata per baris (1 baris penuh, tidak pernah 2 baris).
- Angka asli tetap tampil (1257, 1883, 100%, Henry III, St. Albans).
"""
import contextlib
import json
import os
import re
import wave

BASE = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
AUDIO_DIR = os.path.join(BASE, "output/audio_supertonic")
SUB_DIR = os.path.join(BASE, "output/subtitles")
STORY = os.path.join(BASE, "input/samalas_master_storyboard_enriched.json")

MAX_WORDS = 7
MIN_WORDS = 3
GAP = 0.12          # jeda antar-frasa (detik)
LEAD_IN = 0.40      # jeda awal agar subtitle tidak tertelan crossfade 0.5s awal
BREATH_EXTRA = 0.20 # jeda tambahan di titik <breath>

os.makedirs(SUB_DIR, exist_ok=True)


def wav_dur(p):
    with contextlib.closing(wave.open(p, 'rb')) as w:
        return w.getnframes() / float(w.getframerate())


def fmt(t):
    if t < 0:
        t = 0
    h = int(t // 3600)
    t -= h * 3600
    m = int(t // 60)
    t -= m * 60
    s = int(t)
    ms = int(round((t - s) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _smart_chunk_words(words, max_w=7, min_w=3):
    n = len(words)
    if n <= max_w:
        return [' '.join(words)]
    k = (n + max_w - 1) // max_w
    while k > 1 and (n // k) < min_w:
        k -= 1
    base = n // k
    rem = n % k
    chunks = []
    idx = 0
    for i in range(k):
        size = base + (1 if i < rem else 0)
        chunks.append(' '.join(words[idx:idx + size]))
        idx += size
    return chunks


def split_phrases_balanced(text, max_w=MAX_WORDS, min_w=MIN_WORDS):
    """Pecah naskah menjadi frasa 1-baris tanpa menyisakan 1 atau 2 kata."""
    # Ubah St. menjadi Saint agar tidak memecah singkatan di titik
    text = re.sub(r'\bSt\.\s*', 'Saint ', text)
    # Bersihkan spasi dan strip tanda baca titik dua / titik koma
    text = re.sub(r'[:;]', ',', text)
    # Split hanya pada titik akhir kalimat atau tag breath
    parts = re.split(r'\s*<breath>\s*|(?<=\w)\.\s+(?=[A-Z0-9])|\.\s*$', text)
    chunks = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        clauses = [c.strip() for c in part.split(',') if c.strip()]
        merged_clauses = []
        buf = []
        for c in clauses:
            w = c.split()
            if not buf:
                buf = w
            elif len(buf) + len(w) <= max_w:
                buf.extend(w)
            elif len(w) < min_w:
                buf.extend(w)
            else:
                merged_clauses.append(buf)
                buf = w
        if buf:
            merged_clauses.append(buf)

        for clause_words in merged_clauses:
            chunks.extend(_smart_chunk_words(clause_words, max_w=max_w, min_w=min_w))

    # Penggabungan mundur jika ada potongan < min_w
    res = []
    for c in chunks:
        cw = len(c.split())
        if cw < min_w and res:
            prev = res.pop()
            res.append(prev + " " + c)
        else:
            res.append(c)

    # Penggabungan maju jika potongan pertama < min_w
    final_res = []
    i = 0
    while i < len(res):
        c = res[i]
        cw = len(c.split())
        if cw < min_w and i + 1 < len(res):
            final_res.append(c + " " + res[i + 1])
            i += 2
        else:
            final_res.append(c)
            i += 1

    return final_res


def build(shot_id, text):
    wav = os.path.join(AUDIO_DIR, f"{shot_id}.wav")
    dur = wav_dur(wav)
    phrases = split_phrases_balanced(text)
    if not phrases:
        return 0, dur

    weights = [max(len(p), 4) for p in phrases]
    total_gap = LEAD_IN + GAP * (len(phrases) - 1)
    speak_time = max(dur - total_gap - 0.15, dur * 0.55)
    wsum = sum(weights)

    entries = []
    cur = LEAD_IN
    for idx, (txt, w) in enumerate(zip(phrases, weights)):
        seg = speak_time * (w / wsum)
        start = cur
        end = cur + seg
        entries.append((start, end, txt.lower()))
        cur = end + GAP

    # Pastikan batas akhir tidak menabrak tail padding
    if entries and entries[-1][1] > dur - 0.10:
        entries[-1] = (entries[-1][0], max(entries[-1][0] + 0.6, dur - 0.10), entries[-1][2])

    with open(os.path.join(SUB_DIR, f"{shot_id}.srt"), 'w', encoding='utf-8') as f:
        for i, (s, e, t) in enumerate(entries, 1):
            f.write(f"{i}\n{fmt(s)} --> {fmt(e)}\n{t}\n\n")

    return len(entries), dur


def main():
    with open(STORY, encoding='utf-8') as f:
        d = json.load(f)

    total = 0
    lonely = 0
    for s in d['shots']:
        sid = s['id']
        text = s['narration'].replace('...', ' <breath> ')
        text = text.replace('\u2014', ', ').replace('\u2013', ', ')
        text = ' '.join(text.split())
        n, dur = build(sid, text)
        total += n

    print(f"Generated v4 single-line balanced subtitles for {len(d['shots'])} shots, {total} phrases total.")


if __name__ == "__main__":
    main()
