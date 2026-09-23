"""
gen_subtitles_single_line.py — Subtitle 1-baris, sinkron durasi audio Supertonic, dengan jeda.
Aturan:
- Maksimum 6 kata per baris (SATU baris, tidak pernah 2 baris).
- Timing per-frasa proporsional terhadap jumlah karakter, di dalam durasi WAV Supertonic.
- Jeda (gap) 0.12s antar-frasa + lead-in 0.15s agar tidak terlalu cepat & lebih sinkron.
- Strip tag <breath> dari teks tampilan (hanya jadi penanda jeda tambahan).
Output: output/subtitles/shot_XXX.srt (inline, siap dibakar libass).
"""
import os, re, glob, wave, contextlib, json

BASE = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
AUDIO_DIR = os.path.join(BASE, "output/audio_supertonic")
SUB_DIR = os.path.join(BASE, "output/subtitles")
STORY = os.path.join(BASE, "input/samalas_master_storyboard_enriched.json")

MAX_WORDS = 6
GAP = 0.12          # jeda antar-frasa (detik)
LEAD_IN = 0.15      # jeda awal sebelum frasa pertama
BREATH_EXTRA = 0.18 # jeda tambahan di titik <breath>

os.makedirs(SUB_DIR, exist_ok=True)

def wav_dur(p):
    with contextlib.closing(wave.open(p, 'rb')) as w:
        return w.getnframes() / float(w.getframerate())

def fmt(t):
    if t < 0: t = 0
    h = int(t // 3600); t -= h*3600
    m = int(t // 60);   t -= m*60
    s = int(t)
    ms = int(round((t - s) * 1000))
    if ms == 1000:
        s += 1; ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def split_phrases(text):
    """Pecah ke frasa <=MAX_WORDS kata, hormati <breath> sebagai batas frasa."""
    # tandai breath sebagai pemisah kuat
    segments = re.split(r'\s*<breath>\s*', text)
    phrases = []  # (words_str, is_after_breath)
    for si, seg in enumerate(segments):
        seg = seg.strip().strip(',').strip()
        if not seg:
            continue
        # pecah lagi di koma untuk frasa natural
        commas = [c.strip() for c in seg.split(',') if c.strip()]
        for ci, chunk in enumerate(commas):
            words = chunk.split()
            for i in range(0, len(words), MAX_WORDS):
                piece = ' '.join(words[i:i+MAX_WORDS])
                # frasa pertama tiap segment setelah breath (kecuali segment 0) dapat jeda ekstra
                after_breath = (si > 0 and ci == 0 and i == 0)
                phrases.append((piece.lower(), after_breath))
    return phrases

def build(shot_id, text):
    wav = os.path.join(AUDIO_DIR, f"{shot_id}.wav")
    dur = wav_dur(wav)
    phrases = split_phrases(text)
    if not phrases:
        return
    # bobot durasi berbasis jumlah karakter
    weights = [max(len(p[0]), 4) for p in phrases]
    total_gap = LEAD_IN + GAP * (len(phrases) - 1) + BREATH_EXTRA * sum(1 for p in phrases if p[1])
    speak_time = max(dur - total_gap, dur * 0.6)  # sisakan waktu untuk jeda
    wsum = sum(weights)

    entries = []
    cur = LEAD_IN
    for idx, ((txt, after_breath), w) in enumerate(zip(phrases, weights)):
        if after_breath:
            cur += BREATH_EXTRA
        seg = speak_time * (w / wsum)
        start = cur
        end = cur + seg
        entries.append((start, end, txt))
        cur = end + GAP

    # jangan melewati durasi audio
    if entries and entries[-1][1] > dur:
        entries[-1] = (entries[-1][0], dur, entries[-1][2])

    with open(os.path.join(SUB_DIR, f"{shot_id}.srt"), 'w', encoding='utf-8') as f:
        for i, (s, e, t) in enumerate(entries, 1):
            f.write(f"{i}\n{fmt(s)} --> {fmt(e)}\n{t}\n\n")
    return len(entries), dur

def main():
    with open(STORY, encoding='utf-8') as f:
        d = json.load(f)
    # peta narasi dgn <breath> seperti di script/
    total = 0
    for s in d['shots']:
        sid = s['id']
        text = s['narration'].replace('...', ' <breath> ')
        # em-dash jadi koma supaya jadi batas frasa yang rapi.
        # ANGKA SENGAJA DIBIARKAN ASLI ("1257") — enak dibaca di layar,
        # berbeda dari script TTS yang angkanya dieja.
        text = text.replace('\u2014', ', ').replace('\u2013', ', ')
        text = ' '.join(text.split())
        n, dur = build(sid, text)
        total += n
    print(f"Generated single-line synced subtitles for {len(d['shots'])} shots, {total} phrases total.")

if __name__ == "__main__":
    main()
