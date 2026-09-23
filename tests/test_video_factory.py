import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dashboard import validate_video_request, next_project_dir, create_video_job


def test_validate_video_request_requires_title_and_topic():
    ok, err = validate_video_request({"title": "", "topic": ""})
    assert not ok
    assert "judul" in err.lower()


def test_next_project_dir_picks_next_a_number():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "a001").mkdir()
        (root / "a043").mkdir()
        assert next_project_dir(root).name == "a044"


def test_create_video_job_writes_project_json_and_log():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        req = {
            "title": "Tambora 1815",
            "topic": "Letusan besar yang mengubah iklim dunia.",
            "style": "project404",
            "duration": "8-12 menit",
            "voice": "M2",
            "mode": "step",
            "output": "local+cloud",
        }
        job = create_video_job(req, projects_root=root)
        project = Path(job["project_dir"])
        assert project.name == "a001"
        assert (project / "project.json").exists()
        assert (project / "factory.log").exists()
        data = json.loads((project / "project.json").read_text(encoding="utf-8"))
        assert data["title"] == "Tambora 1815"
        assert data["pipeline"][0]["key"] == "outline"
        assert data["pipeline"][0]["status"] == "pending"
