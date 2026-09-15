# Translation QA Web Viewer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Flask web app (`python3 viewer.py`) that lets QA staff review Korean, Chinese, and Telugu translations — with audio playback, synced captions, and a side-by-side segment table.

**Architecture:** Single `viewer.py` Flask file with three API routes and an embedded HTML template (no separate frontend files, no build step). The template contains all CSS and vanilla JS. Tests live in `tests/test_viewer.py` and use Flask's test client.

**Tech Stack:** Python 3.11+, Flask>=3.0.0, vanilla JS (no npm), pytest

## Global Constraints

- All output data lives under `output/` (gitignored) — never hardcode paths
- `output/final/<lang>/<module>/<stem>.wav` — translated audio
- `output/translations/<lang>/<module>/<stem>.json` — segments with `index`, `start`, `end`, `original`, `translated`
- Languages: `ko` (Korean), `zh` (Chinese (Simplified)), `te` (Telugu)
- Server runs on port 5000 (`python3 viewer.py`)
- No external CDN dependencies — viewer must work offline

---

## File Map

| File | Responsibility |
|---|---|
| `viewer.py` | Flask app — all routes + embedded HTML/CSS/JS template |
| `requirements.txt` | Add `flask>=3.0.0` |
| `tests/test_viewer.py` | Flask test-client tests for all three API routes |

---

### Task 1: Flask Backend + Tests

**Files:**
- Create: `viewer.py`
- Modify: `requirements.txt`
- Create: `tests/test_viewer.py`

**Interfaces:**
- Produces:
  - `GET /` → 200 HTML response
  - `GET /api/index` → `{"languages": ["ko","te","zh"], "lang_names": {"ko":"Korean","zh":"Chinese (Simplified)","te":"Telugu"}, "modules": {"Gen Intro": ["01 Gen Intro_Intro", ...], ...}}`
  - `GET /api/segments/<lang>/<module>/<stem>` → JSON array of `{index, start, end, original, translated}`; 404 if missing
  - `GET /audio/<lang>/<module>/<filename>` → WAV file stream with range support; 404 if missing

- [ ] **Step 1: Add Flask to requirements.txt**

Open `requirements.txt` and add:
```
flask>=3.0.0
```

Then install:
```bash
pip3 install "flask>=3.0.0" --break-system-packages -q
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_viewer.py`:

```python
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
    assert data["lang_names"]["te"] == "Telugu"


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
```

- [ ] **Step 3: Run tests — confirm they fail**

```bash
python3 -m pytest tests/test_viewer.py -v 2>&1 | tail -15
```

Expected: `ModuleNotFoundError: No module named 'viewer'`

- [ ] **Step 4: Create `viewer.py` with all routes**

```python
from flask import Flask, jsonify, send_file, abort
import json
from pathlib import Path

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
TRANSLATIONS_DIR = OUTPUT_DIR / "translations"
FINAL_DIR = OUTPUT_DIR / "final"
LANG_NAMES = {"ko": "Korean", "zh": "Chinese (Simplified)", "te": "Telugu"}

HTML = "<html><body>QA Viewer — coming soon</body></html>"


@app.route("/")
def index():
    return HTML


@app.route("/api/index")
def api_index():
    if not FINAL_DIR.exists():
        return jsonify({"languages": [], "lang_names": {}, "modules": {}})
    languages = sorted(p.name for p in FINAL_DIR.iterdir() if p.is_dir())
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


@app.route("/audio/<lang>/<module>/<filename>")
def audio_file(lang, module, filename):
    path = FINAL_DIR / lang / module / filename
    if not path.exists():
        abort(404)
    return send_file(str(path), conditional=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
python3 -m pytest tests/test_viewer.py -v 2>&1
```

Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add viewer.py requirements.txt tests/test_viewer.py
git commit -m "feat: Flask backend for QA viewer with index, segments, and audio routes"
```

---

### Task 2: HTML Template — Layout, Sidebar, Audio, Captions, Table

**Files:**
- Modify: `viewer.py` — replace the stub `HTML` string with the full template

**Interfaces:**
- Consumes: `/api/index`, `/api/segments/<lang>/<module>/<stem>`, `/audio/<lang>/<module>/<filename>`
- Produces: fully functional single-page viewer

- [ ] **Step 1: Replace the `HTML` stub in `viewer.py` with the full template**

Replace everything from `HTML = "<html>..."` down to (but not including) `@app.route("/")` with:

```python
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Translation QA Viewer</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; height: 100vh; display: flex; flex-direction: column; background: #f5f5f5; color: #222; }

/* Top bar */
#topbar { background: #1a1a2e; color: white; padding: 10px 16px; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
#topbar h1 { font-size: 14px; font-weight: 600; margin-right: auto; letter-spacing: 0.5px; }
.lang-btn { padding: 5px 14px; border: 1px solid rgba(255,255,255,0.35); background: transparent; color: white; border-radius: 4px; cursor: pointer; font-size: 13px; transition: background 0.15s; }
.lang-btn.active { background: white; color: #1a1a2e; font-weight: 600; }
.lang-btn:hover:not(.active) { background: rgba(255,255,255,0.1); }

/* Body */
#body { display: flex; flex: 1; overflow: hidden; }

/* Sidebar */
#sidebar { width: 240px; background: white; border-right: 1px solid #e0e0e0; overflow-y: auto; flex-shrink: 0; }
.module-header { padding: 10px 14px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #888; cursor: pointer; border-bottom: 1px solid #f0f0f0; display: flex; justify-content: space-between; align-items: center; user-select: none; }
.module-header:hover { background: #fafafa; }
.module-parts { display: none; }
.module-parts.open { display: block; }
.part-item { padding: 7px 14px 7px 22px; font-size: 12px; color: #444; cursor: pointer; border-bottom: 1px solid #f9f9f9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.part-item:hover { background: #f0f7ff; color: #1a56db; }
.part-item.active { background: #e8f0fe; color: #1a56db; font-weight: 600; border-left: 3px solid #1a56db; padding-left: 19px; }

/* Main */
#main { flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 14px; gap: 10px; }
#empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: #bbb; font-size: 14px; }

/* Player */
#player-section { background: white; border-radius: 8px; padding: 12px 16px; border: 1px solid #e0e0e0; flex-shrink: 0; display: none; }
#player-title { font-size: 12px; color: #888; margin-bottom: 8px; font-weight: 500; }
audio { width: 100%; height: 36px; }

/* Caption box */
#caption-box { background: white; border-radius: 8px; border: 1px solid #e0e0e0; padding: 16px 24px; min-height: 80px; display: none; align-items: center; justify-content: center; flex-direction: column; gap: 6px; flex-shrink: 0; }
#caption-text { font-size: 20px; text-align: center; line-height: 1.5; color: #111; }
#caption-original { font-size: 12px; color: #aaa; text-align: center; }

/* Segment table */
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
</style>
</head>
<body>

<div id="topbar">
  <h1>Translation QA Viewer</h1>
  <div id="lang-buttons"></div>
</div>

<div id="body">
  <div id="sidebar"></div>
  <div id="main">
    <div id="empty-state">Select a module and part from the sidebar</div>
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
  </div>
</div>

<script>
const state = { lang: null, module: null, stem: null, segments: [], activeIdx: -1 };
const audio = document.getElementById('audio-player');

function srtToSeconds(t) {
  const [time, ms] = t.split(',');
  const [h, m, s] = time.split(':').map(Number);
  return h * 3600 + m * 60 + s + Number(ms) / 1000;
}

function show(id) { document.getElementById(id).style.display = 'flex'; }
function hide(id) { document.getElementById(id).style.display = 'none'; }
function showBlock(id) { document.getElementById(id).style.display = 'block'; }

async function loadIndex() {
  const data = await fetch('/api/index').then(r => r.json());
  state.lang = data.languages[0];

  // Language buttons
  const lb = document.getElementById('lang-buttons');
  data.languages.forEach(lang => {
    const btn = document.createElement('button');
    btn.className = 'lang-btn' + (lang === state.lang ? ' active' : '');
    btn.textContent = data.lang_names[lang] || lang;
    btn.dataset.lang = lang;
    btn.addEventListener('click', () => switchLang(lang));
    lb.appendChild(btn);
  });

  // Sidebar modules
  const sb = document.getElementById('sidebar');
  Object.entries(data.modules).forEach(([mod, parts]) => {
    const header = document.createElement('div');
    header.className = 'module-header';
    header.innerHTML = `<span>${mod}</span><span class="chev">▶</span>`;

    const partList = document.createElement('div');
    partList.className = 'module-parts';

    parts.forEach(stem => {
      const item = document.createElement('div');
      item.className = 'part-item';
      // Strip leading "01 ModuleName_" prefix for display
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

    sb.appendChild(header);
    sb.appendChild(partList);
  });
}

function switchLang(lang) {
  state.lang = lang;
  document.querySelectorAll('.lang-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.lang === lang));
  if (state.stem) {
    const saved = audio.currentTime;
    loadSegments(state.module, state.stem).then(() => { audio.currentTime = saved; });
  }
}

function selectPart(mod, stem, el) {
  state.module = mod;
  state.stem = stem;
  document.querySelectorAll('.part-item').forEach(i => i.classList.remove('active'));
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

  hide('empty-state');
  showBlock('player-section');
  show('caption-box');
  showBlock('table-section');

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
  const t = audio.currentTime;
  const idx = state.segments.findIndex(s => t >= s.startSec && t < s.endSec);
  setActive(idx);
});

loadIndex();
</script>
</body>
</html>"""
```

- [ ] **Step 2: Run existing tests — confirm they still pass**

```bash
python3 -m pytest tests/test_viewer.py -v 2>&1
```

Expected: all 9 tests PASS (the template change doesn't break the routes).

- [ ] **Step 3: Start the server and manually verify**

```bash
python3 viewer.py
```

Open `http://localhost:5000` and verify:

1. **Top bar** shows "Translation QA Viewer" and three language buttons (Korean, Chinese (Simplified), Telugu); Korean is active by default
2. **Sidebar** shows 5 module headers (Gen Intro, Mucositis, Nutrition, Pain Management, Skin Care Management) — all collapsed
3. **Main area** shows "Select a module and part from the sidebar"
4. Click a module header — it expands to show part names; chevron flips from ▶ to ▼
5. Click a part — audio player appears, starts playing; caption box shows "—"; segment table appears with all rows
6. **Caption box** updates text as audio plays — correct translated segment highlighted
7. **Table row** highlights in blue as audio plays, auto-scrolls into view
8. **Click a table row** — audio seeks to that segment and begins playing from that point
9. **Language toggle** — click Chinese (Simplified); audio restarts in Chinese, captions and table update
10. **Switch language mid-play** — audio should restart from position 0

Stop the server with Ctrl+C.

- [ ] **Step 4: Run full test suite**

```bash
python3 -m pytest tests/ -v 2>&1
```

Expected: all 30 tests PASS (21 existing + 9 viewer).

- [ ] **Step 5: Commit**

```bash
git add viewer.py
git commit -m "feat: QA viewer — full HTML template with sidebar, audio player, synced captions, and segment table"
```
