from flask import Flask, jsonify, send_file, abort, Response
import json
import re
from pathlib import Path

from src.modules import MODULES, LANGS, LANG_NAMES

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
TRANSLATIONS_DIR = OUTPUT_DIR / "translations"
FINAL_DIR = OUTPUT_DIR / "final"
DUBBED_DIR = OUTPUT_DIR / "dubbed_elevenlabs"

VIDEO_LABELS = {
    "01_ct_simulation_planning": "CT Simulation Planning",
    "02_radiation_dermatitis_skincare": "Radiation Dermatitis & Skin Care",
    "03_pain_management_overview": "Pain Management Overview",
    "04_mucositis_rinses": "Mucositis & Oral Rinses",
    "05_nutrition_support": "Nutrition Support",
}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Translation QA Viewer</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; height: 100vh; display: flex; flex-direction: column; background: #f5f5f5; color: #222; }

#topbar { background: #1a1a2e; color: white; padding: 10px 16px; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
#topbar h1 { font-size: 14px; font-weight: 600; margin-right: auto; letter-spacing: 0.5px; }
.lang-btn { padding: 5px 14px; border: 1px solid rgba(255,255,255,0.35); background: transparent; color: white; border-radius: 4px; cursor: pointer; font-size: 13px; transition: background 0.15s; }
.lang-btn.active { background: white; color: #1a1a2e; font-weight: 600; }
.lang-btn:hover:not(.active) { background: rgba(255,255,255,0.1); }

#body { display: flex; flex: 1; overflow: hidden; }

#sidebar { width: 240px; background: white; border-right: 1px solid #e0e0e0; overflow-y: auto; flex-shrink: 0; }
.section-divider { padding: 8px 14px 6px; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; color: #bbb; border-bottom: 1px solid #f0f0f0; margin-top: 4px; }
.module-header { padding: 10px 14px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #888; cursor: pointer; border-bottom: 1px solid #f0f0f0; display: flex; justify-content: space-between; align-items: center; user-select: none; }
.module-header:hover { background: #fafafa; }
.module-parts { display: none; }
.module-parts.open { display: block; }
.part-item { padding: 7px 14px 7px 22px; font-size: 12px; color: #444; cursor: pointer; border-bottom: 1px solid #f9f9f9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.part-item:hover { background: #f0f7ff; color: #1a56db; }
.part-item.active { background: #e8f0fe; color: #1a56db; font-weight: 600; border-left: 3px solid #1a56db; padding-left: 19px; }
.video-item { padding: 8px 14px 8px 22px; font-size: 12px; color: #444; cursor: pointer; border-bottom: 1px solid #f9f9f9; }
.video-item:hover { background: #fff5f0; color: #c2410c; }
.video-item.active { background: #fff0e8; color: #c2410c; font-weight: 600; border-left: 3px solid #c2410c; padding-left: 19px; }
.video-item.unavailable { color: #ccc; cursor: default; font-style: italic; }
.video-item.unavailable:hover { background: none; color: #ccc; }

#main { flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 14px; gap: 10px; }
#empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: #bbb; font-size: 14px; }

/* Audio review panel */
#player-section { background: white; border-radius: 8px; padding: 12px 16px; border: 1px solid #e0e0e0; flex-shrink: 0; display: none; }
#player-title { font-size: 12px; color: #888; margin-bottom: 8px; font-weight: 500; }
audio { width: 100%; height: 36px; }

#caption-box { background: white; border-radius: 8px; border: 1px solid #e0e0e0; padding: 16px 24px; min-height: 80px; display: none; align-items: center; justify-content: center; flex-direction: column; gap: 6px; flex-shrink: 0; }
#caption-text { font-size: 20px; text-align: center; line-height: 1.5; color: #111; }
#caption-original { font-size: 12px; color: #aaa; text-align: center; }

#table-section { flex: 1; overflow-y: auto; background: white; border-radius: 8px; border: 1px solid #e0e0e0; display: none; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { position: sticky; top: 0; background: #f8f8f8; padding: 8px 10px; text-align: left; border-bottom: 2px solid #e0e0e0; color: #666; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }
td { padding: 7px 10px; border-bottom: 1px solid #f2f2f2; vertical-align: top; line-height: 1.4; }
tr.seg-row { cursor: pointer; }
tr.seg-row:hover td { background: #f5f9ff; }
tr.seg-row.active td { background: #e8f0fe; }
.col-idx { width: 32px; color: #ccc; font-size: 11px; text-align: right; }
.col-ts { width: 72px; color: #bbb; font-size: 11px; white-space: nowrap; }
.col-orig { color: #555; }
.col-trans { color: #111; font-weight: 500; }

/* Dubbed video panel */
#video-section { flex: 1; display: none; flex-direction: column; gap: 10px; overflow: hidden; }
#video-title { font-size: 12px; color: #888; font-weight: 500; flex-shrink: 0; }
#video-player { width: 100%; flex: 1; background: #000; border-radius: 8px; border: 1px solid #e0e0e0; overflow: hidden; }
#video-player video { width: 100%; height: 100%; object-fit: contain; }
#video-note { font-size: 11px; color: #bbb; text-align: center; flex-shrink: 0; }
</style>
</head>
<body>

<div id="topbar">
  <h1>Translation QA Viewer</h1>
  <div id="lang-buttons"></div>
</div>

<div id="body">
  <div id="sidebar">
    <div id="module-video-sections"></div>
    <div class="section-divider">Dubbed Videos</div>
    <div id="video-list"></div>
    <div class="section-divider">Audio Review</div>
    <div id="module-list"></div>
  </div>
  <div id="main">
    <div id="empty-state">Select a dubbed video or audio part from the sidebar</div>

    <!-- Audio review mode -->
    <div id="player-section">
      <div id="player-title"></div>
      <audio id="audio-player" controls></audio>
    </div>
    <div id="caption-box">
      <div id="caption-text">—</div>
      <div id="caption-original"></div>
    </div>
    <div id="table-section">
      <table>
        <thead><tr>
          <th class="col-idx">#</th>
          <th class="col-ts">Time</th>
          <th class="col-orig">Original</th>
          <th class="col-trans">Translated</th>
        </tr></thead>
        <tbody id="seg-tbody"></tbody>
      </table>
    </div>

    <!-- Dubbed video mode -->
    <div id="video-section">
      <div id="video-title"></div>
      <div id="video-player"><video id="vid" controls preload="metadata"></video></div>
      <div id="video-note">ElevenLabs audio continues after video ends — this is expected.</div>
    </div>
  </div>
</div>

<script>
const LANG_NAMES = {"ko":"Korean","zh":"Chinese (Simplified)","ja":"Japanese","hy":"Armenian","fa":"Farsi (Persian)","es":"Spanish"};
const LANGS = ["ko", "zh", "ja", "hy", "fa", "es"];
const state = {
  lang: null, mode: null,
  module: null, stem: null, segments: [], activeIdx: -1,
  videoKey: null, videosByLang: {},
  moduleData: {},  // moduleKey -> by_lang availability map
  mv: null,        // current module-video selection {key, finalDir, video, stem, label}
};
const audio = document.getElementById('audio-player');
const vid = document.getElementById('vid');

function srtToSeconds(t) {
  const [time, ms] = t.split(',');
  const [h, m, s] = time.split(':').map(Number);
  return h * 3600 + m * 60 + s + Number(ms) / 1000;
}

function show(id) { document.getElementById(id).style.display = 'flex'; }
function hide(id) { document.getElementById(id).style.display = 'none'; }
function showBlock(id) { document.getElementById(id).style.display = 'block'; }

function showAudioMode() {
  hide('video-section');
  hide('empty-state');
  showBlock('player-section');
  show('caption-box');
  showBlock('table-section');
}
function showVideoMode() {
  hide('empty-state');
  hide('player-section');
  hide('caption-box');
  hide('table-section');
  show('video-section');
}

async function loadIndex() {
  const [indexData, videosData, modulesData] = await Promise.all([
    fetch('/api/index').then(r => r.json()),
    fetch('/api/videos').then(r => r.json()),
    fetch('/api/modules').then(r => r.json()),
  ]);

  state.lang = indexData.languages[0];
  state.videosByLang = videosData.by_lang;

  // Language buttons
  const lb = document.getElementById('lang-buttons');
  indexData.languages.forEach(lang => {
    const btn = document.createElement('button');
    btn.className = 'lang-btn' + (lang === state.lang ? ' active' : '');
    btn.textContent = indexData.lang_names[lang] || lang;
    btn.dataset.lang = lang;
    btn.addEventListener('click', () => switchLang(lang));
    lb.appendChild(btn);
  });

  // Module video sections (Gen Intro + Mucositis/Nutrition/Pain Management/Skin Care)
  const ms = document.getElementById('module-video-sections');
  modulesData.modules.forEach(mod => {
    state.moduleData[mod.key] = mod.by_lang;
    const divider = document.createElement('div');
    divider.className = 'section-divider';
    divider.textContent = mod.label + ' Videos';
    ms.appendChild(divider);
    const list = document.createElement('div');
    mod.parts.forEach(part => {
      const item = document.createElement('div');
      item.className = 'video-item';
      item.textContent = part.label;
      item.dataset.mod = mod.key;
      item.dataset.video = part.video;
      item.addEventListener('click', () => selectModuleVideo(mod, part, item));
      list.appendChild(item);
    });
    ms.appendChild(list);
  });

  // Dubbed video list
  const vl = document.getElementById('video-list');
  videosData.videos.forEach(v => {
    const item = document.createElement('div');
    item.className = 'video-item';
    item.textContent = v.label;
    item.dataset.key = v.key;
    item.addEventListener('click', () => selectVideo(v.key, item));
    vl.appendChild(item);
  });

  // Module/part list
  const ml = document.getElementById('module-list');
  Object.entries(indexData.modules).forEach(([mod, parts]) => {
    const header = document.createElement('div');
    header.className = 'module-header';
    header.innerHTML = `<span>${mod}</span><span class="chev">▶</span>`;

    const partList = document.createElement('div');
    partList.className = 'module-parts';

    parts.forEach(stem => {
      const item = document.createElement('div');
      item.className = 'part-item';
      item.textContent = stem.replace(/^\\d+\\s+[^_]+_/, '').replace(/_/g, ' ') || stem;
      item.title = stem;
      item.dataset.module = mod;
      item.dataset.stem = stem;
      item.addEventListener('click', () => selectPart(mod, stem, item));
      partList.appendChild(item);
    });

    header.addEventListener('click', () => {
      const open = partList.classList.toggle('open');
      header.querySelector('.chev').textContent = open ? '▼' : '▶';
    });

    ml.appendChild(header);
    ml.appendChild(partList);
  });

  updateVideoAvailability();
}

function updateVideoAvailability() {
  const availDubbed = state.videosByLang[state.lang] || [];
  document.querySelectorAll('#video-list .video-item').forEach(item => {
    const fname = `${item.dataset.key}_${state.lang}.mp4`;
    if (availDubbed.includes(fname)) {
      item.classList.remove('unavailable');
      item.title = '';
    } else {
      item.classList.add('unavailable');
      item.title = `Not available for ${state.lang}`;
    }
  });

  document.querySelectorAll('#module-video-sections .video-item').forEach(item => {
    const avail = (state.moduleData[item.dataset.mod] || {})[state.lang] || [];
    const fname = `${item.dataset.video}_${state.lang}.mp4`;
    if (avail.includes(fname)) {
      item.classList.remove('unavailable');
      item.title = '';
    } else {
      item.classList.add('unavailable');
      item.title = `Not available for ${state.lang}`;
    }
  });
}

function switchLang(lang) {
  state.lang = lang;
  document.querySelectorAll('.lang-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.lang === lang));
  updateVideoAvailability();
  if (state.mode === 'module' && state.mv) {
    const fname = `${state.mv.video}_${lang}.mp4`;
    const available = (state.moduleData[state.mv.key] || {})[lang] || [];
    if (available.includes(fname)) {
      const t = vid.currentTime;
      vid.src = `/module-video/${encodeURIComponent(state.mv.key)}/${encodeURIComponent(lang)}/${encodeURIComponent(fname)}`;
      setModuleTracks(state.mv.finalDir, state.mv.stem, lang);
      vid.currentTime = t;
    }
  } else if (state.mode === 'video' && state.videoKey) {
    const fname = `${state.videoKey}_${lang}.mp4`;
    const available = state.videosByLang[lang] || [];
    if (available.includes(fname)) {
      const t = vid.currentTime;
      vid.src = `/video/${encodeURIComponent(lang)}/${encodeURIComponent(fname)}`;
      vid.currentTime = t;
    }
  } else if (state.mode === 'segments' && state.stem) {
    const saved = audio.currentTime;
    loadSegments(state.module, state.stem).then(() => { audio.currentTime = saved; });
  }
}

function selectModuleVideo(mod, part, el) {
  const fname = `${part.video}_${state.lang}.mp4`;
  const available = (state.moduleData[mod.key] || {})[state.lang] || [];
  if (!available.includes(fname)) return;

  state.mode = 'module';
  state.mv = {key: mod.key, finalDir: mod.final_dir, video: part.video, stem: part.stem, label: part.label};
  audio.pause();

  document.querySelectorAll('.part-item, .video-item').forEach(i => i.classList.remove('active'));
  el.classList.add('active');

  document.getElementById('video-title').textContent = `${mod.label} — ${part.label} — ${LANG_NAMES[state.lang] || state.lang}`;
  vid.src = `/module-video/${encodeURIComponent(mod.key)}/${encodeURIComponent(state.lang)}/${encodeURIComponent(fname)}`;
  setModuleTracks(mod.final_dir, part.stem, state.lang);
  showVideoMode();
}

function setModuleTracks(finalDir, stem, audioLang) {
  Array.from(vid.querySelectorAll('track')).forEach(t => t.remove());
  LANGS.forEach(lang => {
    const track = document.createElement('track');
    track.kind = 'subtitles';
    track.label = LANG_NAMES[lang] || lang;
    track.srclang = lang;
    // audioLang provides timestamps synced to the playing audio; lang provides translated text
    track.src = `/subtitles/${encodeURIComponent(audioLang)}/${encodeURIComponent(lang)}/${encodeURIComponent(finalDir)}/${encodeURIComponent(stem)}`;
    if (lang === audioLang) track.default = true;
    vid.appendChild(track);
  });
}

function selectVideo(key, el) {
  const fname = `${key}_${state.lang}.mp4`;
  const available = state.videosByLang[state.lang] || [];
  if (!available.includes(fname)) return;

  state.mode = 'video';
  state.videoKey = key;
  audio.pause();

  document.querySelectorAll('.part-item, .video-item').forEach(i => i.classList.remove('active'));
  el.classList.add('active');

  const label = el.textContent;
  document.getElementById('video-title').textContent = `${label} — ${state.lang.toUpperCase()}`;
  vid.src = `/video/${encodeURIComponent(state.lang)}/${encodeURIComponent(fname)}`;
  showVideoMode();
}

function selectPart(mod, stem, el) {
  state.mode = 'segments';
  state.module = mod;
  state.stem = stem;
  vid.pause();

  document.querySelectorAll('.part-item, .video-item').forEach(i => i.classList.remove('active'));
  el.classList.add('active');

  document.getElementById('player-title').textContent = `${mod} — ${stem.replace(/_/g, ' ')}`;
  loadSegments(mod, stem);
}

async function loadSegments(mod, stem) {
  const url = `/api/segments/${encodeURIComponent(state.lang)}/${encodeURIComponent(mod)}/${encodeURIComponent(stem)}`;
  const segs = await fetch(url).then(r => r.json());
  state.segments = segs.map(s => ({
    ...s,
    startSec: srtToSeconds(s.start),
    endSec: srtToSeconds(s.end),
  }));
  audio.src = `/audio/${encodeURIComponent(state.lang)}/${encodeURIComponent(mod)}/${encodeURIComponent(stem)}.wav`;
  showAudioMode();
  renderTable();
  setActive(-1);
}

function renderTable() {
  const tbody = document.getElementById('seg-tbody');
  tbody.innerHTML = '';
  state.segments.forEach((seg, i) => {
    const tr = document.createElement('tr');
    tr.className = 'seg-row';
    tr.dataset.i = i;
    tr.innerHTML =
      `<td class="col-idx">${seg.index}</td>` +
      `<td class="col-ts">${seg.start.slice(0, 8)}</td>` +
      `<td class="col-orig">${escHtml(seg.original)}</td>` +
      `<td class="col-trans">${escHtml(seg.translated)}</td>`;
    tr.addEventListener('click', () => { audio.currentTime = seg.startSec; audio.play(); });
    tbody.appendChild(tr);
  });
}

function setActive(i) {
  if (i === state.activeIdx) return;
  state.activeIdx = i;
  document.querySelectorAll('.seg-row').forEach(r => r.classList.remove('active'));
  if (i >= 0 && i < state.segments.length) {
    const seg = state.segments[i];
    document.getElementById('caption-text').textContent = seg.translated;
    document.getElementById('caption-original').textContent = seg.original;
    const row = document.querySelector(`.seg-row[data-i="${i}"]`);
    if (row) { row.classList.add('active'); row.scrollIntoView({ block: 'nearest' }); }
  } else {
    document.getElementById('caption-text').textContent = '—';
    document.getElementById('caption-original').textContent = '';
  }
}

function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

audio.addEventListener('timeupdate', () => {
  if (state.mode !== 'segments') return;
  const t = audio.currentTime;
  const idx = state.segments.findIndex(s => t >= s.startSec && t < s.endSec);
  setActive(idx);
});

loadIndex();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML


@app.route("/api/index")
def api_index():
    if not FINAL_DIR.exists():
        return jsonify({"languages": [], "lang_names": {}, "modules": {}})
    languages = sorted(p.name for p in FINAL_DIR.iterdir() if p.is_dir() and p.name in LANG_NAMES)
    modules = {}
    ref_lang = next((l for l in languages if (FINAL_DIR / l).exists()), None)
    if ref_lang:
        for mod_dir in sorted((FINAL_DIR / ref_lang).iterdir()):
            if mod_dir.is_dir():
                parts = sorted(p.stem for p in mod_dir.glob("*.wav"))
                if parts:
                    modules[mod_dir.name] = parts
    return jsonify({"languages": languages, "lang_names": LANG_NAMES, "modules": modules})


@app.route("/api/segments/<lang>/<module>/<stem>")
def api_segments(lang, module, stem):
    path = TRANSLATIONS_DIR / lang / module / (stem + ".json")
    if not path.exists():
        abort(404)
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.route("/api/videos")
def api_videos():
    videos = []
    by_lang: dict[str, list[str]] = {}
    for key, label in VIDEO_LABELS.items():
        videos.append({"key": key, "label": label})
    if DUBBED_DIR.exists():
        for lang_dir in sorted(DUBBED_DIR.iterdir()):
            if lang_dir.is_dir():
                by_lang[lang_dir.name] = sorted(p.name for p in lang_dir.glob("*.mp4"))
    return jsonify({"videos": videos, "by_lang": by_lang})


@app.route("/api/modules")
def api_modules():
    modules = []
    for key, mod in MODULES.items():
        by_lang: dict[str, list[str]] = {}
        out_base = OUTPUT_DIR / mod.out_dir
        if out_base.exists():
            for lang_dir in sorted(out_base.iterdir()):
                if lang_dir.is_dir():
                    by_lang[lang_dir.name] = sorted(p.name for p in lang_dir.glob("*.mp4"))
        modules.append({
            "key": key,
            "label": mod.label,
            "final_dir": mod.final_dir,
            "parts": [{"video": p.video, "stem": p.stem, "label": p.label} for p in mod.parts],
            "by_lang": by_lang,
        })
    return jsonify({"modules": modules, "langs": LANGS, "lang_names": LANG_NAMES})


def _parse_srt_blocks(srt_text: str) -> list[tuple[int, str, str]]:
    """Return [(segment_index, vtt_timestamp_line, text), ...]"""
    result = []
    for block in re.split(r'\n{2,}', srt_text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        ts = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', lines[1].strip())
        text = '\n'.join(l.strip() for l in lines[2:])
        result.append((idx, ts, text))
    return result


@app.route("/subtitles/<audio_lang>/<sub_lang>/<module>/<stem>")
def subtitle_file(audio_lang, sub_lang, module, stem):
    # Timing always comes from audio_lang's assembled SRT (synced to its ElevenLabs audio).
    # Text comes from sub_lang's translation JSON (or the same SRT when languages match).
    srt_path = FINAL_DIR / audio_lang / module / (stem + ".srt")
    if not srt_path.exists():
        abort(404)

    srt_text = srt_path.read_text(encoding="utf-8-sig")
    blocks = _parse_srt_blocks(srt_text)

    if audio_lang == sub_lang:
        vtt = "WEBVTT\n\n" + re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", srt_text)
        return Response(vtt, mimetype="text/vtt")

    trans_path = TRANSLATIONS_DIR / sub_lang / module / (stem + ".json")
    if not trans_path.exists():
        abort(404)

    trans_map = {item["index"]: item["translated"]
                 for item in json.loads(trans_path.read_text(encoding="utf-8"))}

    lines = ["WEBVTT", ""]
    for seg_idx, ts, _ in blocks:
        text = trans_map.get(seg_idx, "")
        if text:
            lines += [str(seg_idx), ts, text, ""]

    return Response("\n".join(lines), mimetype="text/vtt")


@app.route("/module-video/<module>/<lang>/<filename>")
def module_video_file(module, lang, filename):
    mod = MODULES.get(module)
    if not mod:
        abort(404)
    path = OUTPUT_DIR / mod.out_dir / lang / filename
    if not path.exists():
        abort(404)
    return send_file(str(path), conditional=True)


@app.route("/audio/<lang>/<module>/<filename>")
def audio_file(lang, module, filename):
    path = FINAL_DIR / lang / module / filename
    if not path.exists():
        abort(404)
    return send_file(str(path), conditional=True)


@app.route("/video/<lang>/<filename>")
def video_file(lang, filename):
    path = DUBBED_DIR / lang / filename
    if not path.exists():
        abort(404)
    return send_file(str(path), conditional=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
