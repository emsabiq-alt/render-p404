import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen_subtitles_single_line import split_phrases_balanced


def test_no_chunks_with_less_than_three_words():
    samples = [
        "dan ribuan jiwa hanyut ditelan amukan lautan.",
        "menumpahkan batu dan abu yang menghujani seluruh daratan.",
        "rumah-rumah roboh dan tersapu banjir lumpur, kerajaan pamatan lenyap terkubur.",
        "menghubungkan jawa, bali, hingga kepulauan maluku.",
        "Di Inggris, seorang biarawan Benediktin bernama Matthew Paris di Biara St. Albans",
        "para bangsawan Inggris memberontak melawan Raja Henry III",
        "Akibatnya, bumi mengalami efek rumah kaca terbalik",
    ]
    for text in samples:
        chunks = split_phrases_balanced(text, max_w=7, min_w=3)
        assert len(chunks) >= 1
        for c in chunks:
            words = c.split()
            assert len(words) >= 3, f"Chunk '{c}' has {len(words)} words in '{text}'"


def test_chunk_lengths_do_not_exceed_max_words():
    long_text = "Sebuah kerucut vulkanik baru lahir dari dalam danau, Gunung Barujari, anak gunung berapi yang terus bertumbuh dan beberapa kali meletus hingga abad ke-21."
    chunks = split_phrases_balanced(long_text, max_w=7, min_w=3)
    for c in chunks:
        words = c.split()
        assert len(words) <= 8, f"Chunk '{c}' has {len(words)} words"
