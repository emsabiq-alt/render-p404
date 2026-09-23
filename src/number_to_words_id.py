"""
number_to_words_id.py — Konversi angka ke kata Bahasa Indonesia untuk TTS.
Menangani:
  1257           -> "seribu dua ratus lima puluh tujuh"
  4.200 / 4200   -> "empat ribu dua ratus"
  ke-20          -> "ke dua puluh"
  ke-13          -> "ke tiga belas"
Dipakai sebelum teks dikirim ke Supertonic, karena Supertonic tidak
mengeja angka Indonesia dengan benar (dibaca per-digit / dilewati).
"""
import re

SATUAN = ["nol", "satu", "dua", "tiga", "empat", "lima",
          "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"]


def _under_1000(n):
    """0..999 -> kata."""
    if n < 12:
        return SATUAN[n]
    if n < 20:
        return SATUAN[n - 10] + " belas"
    if n < 100:
        puluh, sisa = divmod(n, 10)
        out = SATUAN[puluh] + " puluh"
        if sisa:
            out += " " + SATUAN[sisa]
        return out
    # 100..999
    ratus, sisa = divmod(n, 100)
    out = "seratus" if ratus == 1 else SATUAN[ratus] + " ratus"
    if sisa:
        out += " " + _under_1000(sisa)
    return out


def number_to_words(n):
    """Integer non-negatif -> kata Bahasa Indonesia."""
    n = int(n)
    if n == 0:
        return "nol"
    if n < 1000:
        return _under_1000(n)
    if n < 1_000_000:
        ribu, sisa = divmod(n, 1000)
        out = "seribu" if ribu == 1 else _under_1000(ribu) + " ribu"
        if sisa:
            out += " " + _under_1000(sisa)
        return out
    if n < 1_000_000_000:
        juta, sisa = divmod(n, 1_000_000)
        out = _under_1000(juta) + " juta"
        if sisa:
            out += " " + number_to_words(sisa)
        return out
    milyar, sisa = divmod(n, 1_000_000_000)
    out = _under_1000(milyar) + " milyar"
    if sisa:
        out += " " + number_to_words(sisa)
    return out


def _repl_ordinal(m):
    """ke-20 -> 'ke dua puluh'"""
    return "ke " + number_to_words(m.group(1))


def _repl_number(m):
    """1.257 / 1257 -> kata. Titik/koma sebagai pemisah ribuan dibuang."""
    raw = m.group(0)
    cleaned = raw.replace(".", "").replace(",", "")
    if not cleaned.isdigit():
        return raw
    return number_to_words(cleaned)


def normalize_numbers(text):
    """Ubah semua angka dalam teks menjadi kata Bahasa Indonesia."""
    # ordinal dulu (ke-20, ke-13) supaya tidak ketangkap aturan umum
    text = re.sub(r"\bke-(\d+)\b", _repl_ordinal, text)
    # angka biasa, termasuk pemisah ribuan titik/koma
    text = re.sub(r"\b\d[\d.,]*\b", _repl_number, text)
    # rapikan spasi ganda
    text = re.sub(r"\s{2,}", " ", text)
    return text


def normalize_for_tts(text):
    """Normalisasi lengkap sebelum masuk TTS: angka + tanda baca khusus."""
    # em-dash / en-dash jadi koma agar dibaca sebagai jeda wajar, bukan simbol
    text = text.replace("\u2014", ", ").replace("\u2013", ", ")
    # kutip melengkung -> lurus
    text = (text.replace("\u201c", '"').replace("\u201d", '"')
                .replace("\u2018", "'").replace("\u2019", "'"))
    text = normalize_numbers(text)
    # rapikan koma ganda / spasi sebelum koma
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*,+", ",", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


if __name__ == "__main__":
    cases = [
        ("Tahun 1257 Masehi", "seribu dua ratus lima puluh tujuh"),
        ("tingginya 4.200 meter", "empat ribu dua ratus"),
        ("abad ke-20", "ke dua puluh"),
        ("abad ke-13", "ke tiga belas"),
        ("1258 dan 1259", "seribu dua ratus lima puluh delapan"),
        ("letusan 1883", "seribu delapan ratus delapan puluh tiga"),
        ("sekitar 750 kilometer", "tujuh ratus lima puluh"),
        ("100 tahun", "seratus"),
        ("43 kali", "empat puluh tiga"),
        ("tahun 1990", "seribu sembilan ratus sembilan puluh"),
        ("abad ke-21", "ke dua puluh satu"),
        ("hanya 1 orang", "satu"),
        ("11 hari", "sebelas"),
        ("12 bulan", "dua belas"),
    ]
    ok = 0
    for src, expect in cases:
        got = normalize_numbers(src)
        passed = expect in got
        ok += passed
        print(("PASS" if passed else "FAIL"), f"{src!r} -> {got!r}")
        assert passed, f"expected {expect!r} inside {got!r}"

    # uji normalize_for_tts: em-dash jadi koma, angka tetap dieja
    t = normalize_for_tts("di dunia\u2014sebuah gunung selama 750 tahun.")
    assert "\u2014" not in t, t
    assert "tujuh ratus lima puluh" in t, t
    print("PASS em-dash ->", repr(t))

    t2 = normalize_for_tts("laut\u2014jauh lebih tinggi")
    assert t2 == "laut, jauh lebih tinggi", repr(t2)
    print("PASS em-dash spasi ->", repr(t2))

    print(f"\n{ok}/{len(cases)} lulus + 2 uji normalisasi")
