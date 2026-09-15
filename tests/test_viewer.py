import pytest
from viewer import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_root_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<html" in resp.data.lower()


def test_api_index_structure(client):
    resp = client.get("/api/index")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "languages" in data
    assert "modules" in data
    assert "lang_names" in data
    assert isinstance(data["languages"], list)
    assert isinstance(data["modules"], dict)


def test_api_index_includes_known_language(client):
    data = client.get("/api/index").get_json()
    assert "ko" in data["languages"]


def test_api_index_includes_known_module(client):
    data = client.get("/api/index").get_json()
    assert "Gen Intro" in data["modules"]


def test_api_index_lang_names(client):
    data = client.get("/api/index").get_json()
    assert data["lang_names"]["ko"] == "Korean"
    assert data["lang_names"]["zh"] == "Chinese (Simplified)"
    assert data["lang_names"]["ja"] == "Japanese"
    assert "te" not in data["lang_names"]


def test_api_segments_returns_array(client):
    resp = client.get("/api/segments/ko/Gen Intro/01 Gen Intro_Intro")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) > 0
    seg = data[0]
    assert "index" in seg
    assert "start" in seg
    assert "end" in seg
    assert "original" in seg
    assert "translated" in seg


def test_api_segments_404_on_missing(client):
    resp = client.get("/api/segments/ko/FakeModule/nonexistent")
    assert resp.status_code == 404


def test_audio_route_200(client):
    resp = client.get("/audio/ko/Gen Intro/01 Gen Intro_Intro.wav")
    assert resp.status_code == 200


def test_audio_route_404_on_missing(client):
    resp = client.get("/audio/ko/FakeModule/nonexistent.wav")
    assert resp.status_code == 404


def test_api_videos_structure(client):
    resp = client.get("/api/videos")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "videos" in data
    assert "by_lang" in data
    assert isinstance(data["videos"], list)
    assert len(data["videos"]) == 5
    assert all("key" in v and "label" in v for v in data["videos"])


def test_api_videos_has_ko_and_zh(client):
    data = client.get("/api/videos").get_json()
    assert "ko" in data["by_lang"]
    assert "zh" in data["by_lang"]
    assert len(data["by_lang"]["ko"]) == 5
    assert len(data["by_lang"]["zh"]) == 5


def test_video_route_200(client):
    resp = client.get("/video/ko/04_mucositis_rinses_ko.mp4")
    assert resp.status_code == 200


def test_video_route_404_on_missing(client):
    resp = client.get("/video/ko/nonexistent.mp4")
    assert resp.status_code == 404


def test_api_modules_structure(client):
    resp = client.get("/api/modules")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "modules" in data
    assert "langs" in data
    keys = {m["key"] for m in data["modules"]}
    assert {"gen-intro", "mucositis", "nutrition", "pain-management", "skincare"} <= keys
    for m in data["modules"]:
        assert "label" in m and "final_dir" in m and "parts" in m and "by_lang" in m
        assert all("video" in p and "stem" in p and "label" in p for p in m["parts"])


def test_api_modules_gen_intro_has_ten_parts(client):
    data = client.get("/api/modules").get_json()
    gi = next(m for m in data["modules"] if m["key"] == "gen-intro")
    assert len(gi["parts"]) == 10
    for lang in ["ko", "zh", "ja", "hy", "fa"]:
        assert len(gi["by_lang"][lang]) == 10


def test_api_modules_new_module_part_counts(client):
    data = client.get("/api/modules").get_json()
    counts = {m["key"]: len(m["parts"]) for m in data["modules"]}
    assert counts["mucositis"] == 7
    assert counts["nutrition"] == 7
    assert counts["pain-management"] == 3
    assert counts["skincare"] == 4


def test_module_video_route_200(client):
    resp = client.get("/module-video/gen-intro/ko/gen_intro_v1_ko.mp4")
    assert resp.status_code == 200


def test_module_video_route_404_on_missing(client):
    resp = client.get("/module-video/gen-intro/ko/nonexistent.mp4")
    assert resp.status_code == 404


def test_module_video_route_404_on_bad_module(client):
    resp = client.get("/module-video/not-a-module/ko/x.mp4")
    assert resp.status_code == 404


def test_subtitle_route_new_module(client):
    resp = client.get("/subtitles/ko/zh/Mucositis/01 Mucositis_Intro")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/vtt")


def test_subtitle_route_same_lang_returns_vtt(client):
    resp = client.get("/subtitles/ko/ko/Gen Intro/01 Gen Intro_Intro")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/vtt")
    assert resp.data.startswith(b"WEBVTT")


def test_subtitle_route_cross_lang_returns_vtt(client):
    resp = client.get("/subtitles/ko/zh/Gen Intro/01 Gen Intro_Intro")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/vtt")
    assert resp.data.startswith(b"WEBVTT")


def test_subtitle_route_cross_lang_uses_audio_timing(client):
    ko_resp = client.get("/subtitles/ko/ko/Gen Intro/01 Gen Intro_Intro")
    cross_resp = client.get("/subtitles/ko/zh/Gen Intro/01 Gen Intro_Intro")
    # Both should have identical timestamps (from ko timing)
    ko_lines = [l for l in ko_resp.data.decode().splitlines() if "-->" in l]
    cross_lines = [l for l in cross_resp.data.decode().splitlines() if "-->" in l]
    assert ko_lines == cross_lines


def test_subtitle_route_404_on_missing(client):
    resp = client.get("/subtitles/ko/ko/FakeModule/nonexistent")
    assert resp.status_code == 404
