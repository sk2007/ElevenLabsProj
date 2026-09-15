from pathlib import Path

from src.module_dubber import build_ffmpeg_cmd, compute_output_duration


def test_build_ffmpeg_cmd_maps_video_audio_and_subs():
    srts = [("ko", Path("ko.srt")), ("zh", Path("zh.srt")), ("ja", Path("ja.srt"))]
    cmd = build_ffmpeg_cmd(Path("src.mp4"), Path("audio.wav"), srts, Path("out.mp4"))

    # Inputs: video, wav, then one per srt
    assert cmd[:5] == ["ffmpeg", "-y", "-i", "src.mp4", "-i"]
    assert cmd.count("-i") == 2 + len(srts)

    # Video from input 0, audio from input 1
    assert "-map" in cmd
    assert "0:v:0" in cmd
    assert "1:a:0" in cmd
    # Subtitle streams mapped from inputs 2..n
    assert "2:s:0" in cmd
    assert "4:s:0" in cmd

    # Codecs
    assert "copy" in cmd  # video copy
    assert "mov_text" in cmd

    # Subtitle language metadata uses ISO 639-2 codes
    assert "language=kor" in cmd
    assert "language=zho" in cmd
    assert "language=jpn" in cmd

    assert cmd[-1] == "out.mp4"


def test_build_ffmpeg_cmd_no_subs():
    cmd = build_ffmpeg_cmd(Path("src.mp4"), Path("audio.wav"), [], Path("out.mp4"))
    assert cmd.count("-i") == 2
    assert "0:v:0" in cmd and "1:a:0" in cmd
    assert not any(s.endswith(":s:0") for s in cmd)


def test_build_ffmpeg_cmd_no_duration_has_no_t_flag():
    cmd = build_ffmpeg_cmd(Path("s.mp4"), Path("a.wav"), [], Path("o.mp4"))
    assert "-t" not in cmd


def test_build_ffmpeg_cmd_duration_appends_t_flag_before_output():
    cmd = build_ffmpeg_cmd(Path("s.mp4"), Path("a.wav"), [], Path("o.mp4"), duration=52.4)
    assert "-t" in cmd
    ti = cmd.index("-t")
    assert cmd[ti + 1] == "52.400"
    assert cmd[ti + 1] != cmd[-1]  # -t value is not the output path (comes before it)
    assert cmd[-1] == "o.mp4"


# compute_output_duration: trim target = later of caption end and dubbed audio
# end; only trim (return a cap) when that target is shorter than the source video.
def test_trim_removes_silent_tail_capped_at_caption_end():
    # audio ends at 40, English narration at 52, video runs 118 → trim to 52
    assert compute_output_duration(video_dur=118.0, audio_dur=40.0, caption_end=52.0) == 52.0


def test_trim_uses_audio_end_when_it_exceeds_caption_end():
    # dub is longer than the original narration → keep audio, trim dead tail to audio end
    assert compute_output_duration(video_dur=118.0, audio_dur=90.0, caption_end=52.0) == 90.0


def test_no_trim_when_audio_overruns_video():
    # Farsi dub longer than the video → never cut audio
    assert compute_output_duration(video_dur=99.9, audio_dur=120.5, caption_end=96.5) is None


def test_no_trim_when_caption_end_reaches_video_end():
    assert compute_output_duration(video_dur=92.2, audio_dur=59.0, caption_end=92.0) is None


def test_no_trim_for_negligible_tail():
    # target within epsilon of the video length → not worth re-cutting
    assert compute_output_duration(video_dur=65.9, audio_dur=51.0, caption_end=65.8) is None


def test_missing_caption_end_falls_back_to_audio():
    assert compute_output_duration(video_dur=118.0, audio_dur=40.0, caption_end=None) == 40.0
