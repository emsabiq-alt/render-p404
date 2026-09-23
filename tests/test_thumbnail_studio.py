import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thumbnail_studio import (
    viral_titles,
    youtube_description,
    format_ts,
    build_thumbnail_pack,
)


def test_viral_titles_are_three_uppercase_mobile_safe():
    titles = viral_titles()
    assert len(titles) == 3
    assert all(t == t.upper() for t in titles)
    assert all(len(t) <= 55 for t in titles)


def test_format_ts_outputs_youtube_timestamp():
    assert format_ts(0) == "00:00"
    assert format_ts(61.2) == "01:01"
    assert format_ts(3671) == "1:01:11"


def test_description_contains_chapters_and_music_credit():
    desc = youtube_description([("PROLOG", 0), ("BAB 1", 12.4)])
    assert "00:00 PROLOG" in desc
    assert "00:12 BAB 1" in desc
    assert "Ossuary 5 - Rest" in desc
    assert "Prelude and Action" in desc


def test_build_thumbnail_pack_writes_three_png_and_metadata(tmp_path):
    pack = build_thumbnail_pack(tmp_path)
    assert len(pack["thumbnails"]) == 3
    assert Path(pack["metadata_path"]).exists()
    for item in pack["thumbnails"]:
        p = Path(item["path"])
        assert p.exists()
        assert p.suffix == ".png"
    data = json.loads(Path(pack["metadata_path"]).read_text(encoding="utf-8"))
    assert len(data["titles"]) == 3
    assert "description" in data
