from pathlib import Path

from src.exporter import build_burn_cmd


def test_build_burn_cmd_burns_subtitle_and_copies_audio():
    cmd = build_burn_cmd(Path("in.mp4"), Path("sub.srt"), Path("out.mp4"))
    assert cmd[:4] == ["ffmpeg", "-y", "-i", "in.mp4"]
    # video re-encoded, audio copied
    assert "-c:v" in cmd and "libx264" in cmd
    ai = cmd.index("-c:a")
    assert cmd[ai + 1] == "copy"
    # subtitle burned via the subtitles filter
    vi = cmd.index("-vf")
    assert cmd[vi + 1] == "subtitles=sub.srt"
    # only video+audio mapped (no subtitle stream carried through)
    assert "0:v:0" in cmd and "0:a:0" in cmd
    assert cmd[-1] == "out.mp4"
