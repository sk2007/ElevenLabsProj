"""Savjani Lab - Dubbing Pipeline Interactive Demo.

Focused specifically on the flagship introductory video:
  Module: General Introduction ("Gen Intro")
  Part: Intro ("01 Gen Intro_Intro", video: gen_intro_v1)
  Title: "What is radiation therapy and what to expect?"

Demonstrates the complete 4-stage pipeline:
  Stage 1: Subtitle Translation (OpenAI GPT-4o Oncology Model)
  Stage 2: Voice Synthesis (ElevenLabs eleven_multilingual_v2 TTS)
  Stage 3: Audio Assembly & Timestamp Recalculation (FFmpeg + FFprobe)
  Stage 4: Dubbed Video Orchestration (Stream Muxing & Embedded Subtitles)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from flask import Flask, jsonify, send_file, abort, Response, render_template_string

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.modules import MODULES, LANGS, LANG_NAMES, LANG_SUB_CODE
from src.srt_parser import parse_srt

app = Flask(__name__)

CAPTIONS_DIR = BASE_DIR / "Captions"
OUTPUT_DIR = BASE_DIR / "output"
TRANSLATIONS_DIR = OUTPUT_DIR / "translations"
AUDIO_RAW_DIR = OUTPUT_DIR / "audio_raw"
FINAL_DIR = OUTPUT_DIR / "final"

# Target video for the demo: first video in the library
DEMO_MODULE_KEY = "gen-intro"
DEMO_MODULE = MODULES[DEMO_MODULE_KEY]
DEMO_PART = DEMO_MODULE.parts[0]  # Part("gen_intro_v1", "01 Gen Intro_Intro", "Intro")

DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pipeline Workflow Demo | Gen Intro</title>
<style>
  :root {
    --primary: #2563eb;
    --primary-hover: #1d4ed8;
    --stage1: #7c3aed;
    --stage2: #0284c7;
    --stage3: #d97706;
    --stage4: #059669;
    --bg: #f8fafc;
    --card: #ffffff;
    --text: #0f172a;
    --text-muted: #64748b;
    --border: #e2e8f0;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }

  /* Header */
  header {
    background: #0f172a;
    color: #fff;
    padding: 18px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 4px rgba(0,0,0,0.12);
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .header-title {
    font-size: 19px;
    font-weight: 700;
    letter-spacing: -0.3px;
  }
  .badge {
    background: #1e293b;
    border: 1px solid #334155;
    color: #94a3b8;
    font-size: 11px;
    padding: 3px 9px;
    border-radius: 9999px;
    font-weight: 500;
  }
  .badge-highlight {
    background: rgba(37, 99, 235, 0.2);
    border-color: #3b82f6;
    color: #60a5fa;
  }

  /* Sticky Focus Banner */
  .focus-bar {
    background: #ffffff;
    border-bottom: 1px solid var(--border);
    padding: 12px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
    position: sticky;
    top: 0;
    z-index: 20;
  }
  .video-target-info {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
  }
  .video-tag {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    color: #334155;
    font-family: monospace;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
  }
  .lang-picker {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .lang-picker label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .lang-btn {
    border: 1px solid var(--border);
    background: #fff;
    color: #334155;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .lang-btn:hover {
    background: #f1f5f9;
  }
  .lang-btn.active {
    background: #0f172a;
    color: #ffffff;
    border-color: #0f172a;
  }

  main {
    max-width: 1300px;
    margin: 24px auto 60px auto;
    padding: 0 32px;
  }

  /* 4-Stage Stepper Cards */
  .stepper-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }
  .step-card {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 18px;
    cursor: pointer;
    position: relative;
    transition: all 0.18s ease;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .step-card:hover {
    border-color: #94a3b8;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.04);
  }
  .step-card.active {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
  }
  .step-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    border-radius: 8px 8px 0 0;
  }
  .step-card.s1::before { background: var(--stage1); }
  .step-card.s2::before { background: var(--stage2); }
  .step-card.s3::before { background: var(--stage3); }
  .step-card.s4::before { background: var(--stage4); }
  .step-num {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-muted);
  }
  .step-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--text);
  }
  .step-desc {
    font-size: 12px;
    color: var(--text-muted);
  }

  /* Panel Container */
  .panel {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 28px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  }
  .panel-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 1px solid var(--border);
    padding-bottom: 16px;
    margin-bottom: 20px;
  }
  .panel-top h2 {
    font-size: 18px;
    font-weight: 700;
  }
  .panel-top p {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 4px;
  }
  .spec-badge {
    background: #f1f5f9;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    color: #334155;
    display: inline-flex;
    gap: 8px;
  }

  /* Code / Architecture Box */
  .code-container {
    background: #0f172a;
    color: #e2e8f0;
    border-radius: 8px;
    padding: 14px 18px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
    line-height: 1.6;
    margin: 16px 0 20px 0;
    overflow-x: auto;
  }
  .code-comment { color: #64748b; }
  .code-key { color: #38bdf8; font-weight: 600; }
  .code-val { color: #fde047; }

  /* Tables */
  .table-scroll {
    overflow-x: auto;
    max-height: 520px;
    overflow-y: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    text-align: left;
  }
  th {
    background: #f8fafc;
    padding: 10px 14px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 2;
  }
  td {
    padding: 10px 14px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: top;
  }
  tr:hover td {
    background: #f8fafc;
  }
  .ts {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 11px;
    background: #f1f5f9;
    padding: 2px 6px;
    border-radius: 4px;
    color: #475569;
    white-space: nowrap;
  }
  .ts-recalc {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 11px;
    background: #eff6ff;
    color: #1d4ed8;
    padding: 2px 6px;
    border-radius: 4px;
    white-space: nowrap;
  }

  /* Segment Audio Grid */
  .segments-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: 550px;
    overflow-y: auto;
    padding-right: 6px;
  }
  .segment-card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: #ffffff;
    transition: background 0.15s;
  }
  .segment-card:hover {
    background: #f8fafc;
  }
  .segment-idx {
    font-weight: 700;
    font-size: 13px;
    color: var(--text-muted);
    width: 32px;
    text-align: center;
  }
  .segment-body {
    flex: 1;
    min-width: 0;
  }
  .segment-text {
    font-size: 13px;
    font-weight: 500;
    color: #0f172a;
    line-height: 1.4;
  }
  .segment-meta {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
    display: flex;
    gap: 10px;
    align-items: center;
  }
  audio {
    height: 34px;
  }

  /* Video Players Side-by-Side */
  .video-dual-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-top: 16px;
  }
  .video-col {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .video-col h3 {
    font-size: 14px;
    font-weight: 700;
    color: #334155;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .video-wrapper {
    background: #000;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }
  video {
    width: 100%;
    display: block;
    max-height: 400px;
  }

  .delta-pill {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
  }
  .delta-pos { background: #fee2e2; color: #b91c1c; }
  .delta-neg { background: #dcfce7; color: #15803d; }
  .delta-zero { background: #f1f5f9; color: #64748b; }
</style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="header-title">Savjani Lab • Video Dubbing Pipeline Demo</div>
    <span class="badge badge-highlight">Target: Gen Intro — Intro</span>
  </div>
  <div>
    <span class="badge">OpenAI GPT-4o + ElevenLabs Multilingual v2</span>
  </div>
</header>

<div class="focus-bar">
  <div class="video-target-info">
    <span style="font-weight: 600;">Library Video:</span>
    <span class="video-tag">gen_intro_v1_multisub.mp4</span>
    <span style="color: var(--text-muted);">(Part 1: "What is radiation therapy and what to expect?")</span>
  </div>

  <div class="lang-picker">
    <label>Target Language:</label>
    <div id="lang-buttons" style="display: flex; gap: 6px;"></div>
  </div>
</div>

<main>
  <!-- 4-Stage Stepper Navigation -->
  <div class="stepper-grid">
    <div class="step-card s1 active" id="btn-stage-1" onclick="selectStage(1)">
      <div class="step-num">Stage 1</div>
      <div class="step-title">Subtitle Translation</div>
      <div class="step-desc">OpenAI GPT-4o medical translation</div>
    </div>
    <div class="step-card s2" id="btn-stage-2" onclick="selectStage(2)">
      <div class="step-num">Stage 2</div>
      <div class="step-title">ElevenLabs Synthesis</div>
      <div class="step-desc">Segmented TTS voice generation</div>
    </div>
    <div class="step-card s3" id="btn-stage-3" onclick="selectStage(3)">
      <div class="step-num">Stage 3</div>
      <div class="step-title">Assembly & Retiming</div>
      <div class="step-desc">FFmpeg concat & SRT recalculation</div>
    </div>
    <div class="step-card s4" id="btn-stage-4" onclick="selectStage(4)">
      <div class="step-num">Stage 4</div>
      <div class="step-title">Dubbed Video Dubbing</div>
      <div class="step-desc">Orchestration & multi-sub muxing</div>
    </div>
  </div>

  <!-- Stage 1 Panel: Translation -->
  <section id="panel-stage-1" class="panel">
    <div class="panel-top">
      <div>
        <h2>Stage 1: Subtitle Translation (OpenAI GPT-4o)</h2>
        <p>Source English subtitles parsed into 23 segments and translated with oncology-specific accuracy.</p>
      </div>
      <div class="spec-badge">
        <span>Model: gpt-4o</span>
        <span>•</span>
        <span>Source: Captions/Gen Intro/01 Gen Intro_Intro.srt</span>
      </div>
    </div>

    <div class="code-container">
      <span class="code-comment">// Translation Prompt Architecture (src/translator.py)</span><br>
      <span class="code-key">System Role:</span> "You are a medical translator specializing in oncology patient education."<br>
      <span class="code-key">Instruction:</span> "Translate ALL of the following English segments into <span class="code-val" id="spec-lang-name">Spanish</span>. Preserve medical terminology accuracy. Keep translations concise — they will be spoken aloud."<br>
      <span class="code-key">Format:</span> JSON array: [{"index": 1, "translated": "..."}, {"index": 2, "translated": "..."}]
    </div>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th style="width: 45px;">#</th>
            <th style="width: 190px;">Source Timecode (SRT)</th>
            <th style="width: 44%;">Original English Subtitle</th>
            <th>Translated (<span class="target-lang-name">Spanish</span>)</th>
          </tr>
        </thead>
        <tbody id="stage1-tbody"></tbody>
      </table>
    </div>
  </section>

  <!-- Stage 2 Panel: ElevenLabs TTS -->
  <section id="panel-stage-2" class="panel" style="display: none;">
    <div class="panel-top">
      <div>
        <h2>Stage 2: Voice Synthesis (ElevenLabs API)</h2>
        <p>Each translated text line is converted to natural human-like speech using ElevenLabs Multilingual v2.</p>
      </div>
      <div class="spec-badge">
        <span>Voice: Rachel (21m00Tcm4TlvDq8ikWAM)</span>
        <span>•</span>
        <span>Model: eleven_multilingual_v2</span>
        <span>•</span>
        <span>Output: MP3 44.1kHz</span>
      </div>
    </div>

    <div class="code-container">
      <span class="code-comment">// ElevenLabs API Invocation (src/synthesizer.py)</span><br>
      client.text_to_speech.convert(<br>
      &nbsp;&nbsp;voice_id=<span class="code-val">"21m00Tcm4TlvDq8ikWAM"</span>,  <span class="code-comment">// Rachel female voice</span><br>
      &nbsp;&nbsp;model_id=<span class="code-val">"eleven_multilingual_v2"</span>, <span class="code-comment">// Multilingual consistency</span><br>
      &nbsp;&nbsp;output_format=<span class="code-val">"mp3_44100_128"</span>,<br>
      &nbsp;&nbsp;text=seg[<span class="code-val">"translated"</span>]<br>
      )
    </div>

    <div class="segments-container" id="stage2-list"></div>
  </section>

  <!-- Stage 3 Panel: Audio Assembly & Retiming -->
  <section id="panel-stage-3" class="panel" style="display: none;">
    <div class="panel-top">
      <div>
        <h2>Stage 3: Audio Assembly & Timestamp Recalculation</h2>
        <p>Individual audio clips are concatenated with FFmpeg, and subtitle timestamps are rebuilt from ffprobe duration measurements.</p>
      </div>
      <div class="spec-badge">
        <span>Format: 44.1kHz Mono WAV</span>
        <span>•</span>
        <span>Timestamp Engine: ffprobe actual audio duration</span>
      </div>
    </div>

    <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; margin-bottom: 20px;">
      <div style="font-size: 13px; font-weight: 700; margin-bottom: 6px; color: #334155;">
        Complete Assembled Dubbed Master Audio (<span class="target-lang-name">Spanish</span>)
      </div>
      <audio id="master-wav-player" controls style="width: 100%;"></audio>
    </div>

    <div class="code-container">
      <span class="code-comment">// Why recalculate timestamps? (src/assembler.py)</span><br>
      <span class="code-comment">// Synthesized languages naturally take longer or shorter to speak than the original English.</span><br>
      <span class="code-key">1.</span> ffprobe measures exact duration of each segment MP3<br>
      <span class="code-key">2.</span> FFmpeg concatenates all segment clips into master WAV<br>
      <span class="code-key">3.</span> Recalculate SRT timestamps cumulatively: <span class="code-val">start = cursor</span>, <span class="code-val">cursor += duration</span>, <span class="code-val">end = cursor</span>
    </div>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th style="width: 45px;">#</th>
            <th style="width: 200px;">Original English Timing</th>
            <th style="width: 200px;">Recalculated (<span class="target-lang-name">Spanish</span>) Timing</th>
            <th>Timing Adjustment & Alignment</th>
          </tr>
        </thead>
        <tbody id="stage3-tbody"></tbody>
      </table>
    </div>
  </section>

  <!-- Stage 4 Panel: Dubbed Video Orchestration -->
  <section id="panel-stage-4" class="panel" style="display: none;">
    <div class="panel-top">
      <div>
        <h2>Stage 4: Dubbed Video Orchestration & Multi-track Subtitle Muxing</h2>
        <p>Muxes source video track with the newly assembled dubbed audio, embeds all language subtitle tracks as mov_text, and trims dead tail space.</p>
      </div>
      <div class="spec-badge">
        <span>Video: -c:v copy</span>
        <span>•</span>
        <span>Audio: AAC 192k</span>
        <span>•</span>
        <span>Subtitles: mov_text</span>
      </div>
    </div>

    <div class="code-container">
      <span class="code-comment">// Orchestration Command Executed (src/module_dubber.py)</span><br>
      ffmpeg -y -i gen_intro_v1_multisub.mp4 -i 01_Gen_Intro_Intro_<span class="code-val" id="cmd-lang">es</span>.wav \\<br>
      &nbsp;&nbsp;-i final_ko.srt -i final_zh.srt -i final_ja.srt -i final_hy.srt -i final_fa.srt -i final_es.srt \\<br>
      &nbsp;&nbsp;-map 0:v:0 -map 1:a:0 -map 2:s:0 -map 3:s:0 -map 4:s:0 -map 5:s:0 -map 6:s:0 -map 7:s:0 \\<br>
      &nbsp;&nbsp;-c:v copy -c:a aac -b:a 192k -c:s mov_text \\<br>
      &nbsp;&nbsp;-metadata:s:s:0 language=kor -metadata:s:s:1 language=zho -metadata:s:s:2 language=jpn ... \\<br>
      &nbsp;&nbsp;-t 92.694 output/gen_intro_dubbed/<span class="code-val" id="cmd-lang-out">es</span>/gen_intro_v1_<span class="code-val" id="cmd-lang-file">es</span>.mp4
    </div>

    <div class="video-dual-grid">
      <!-- Original Source Video -->
      <div class="video-col">
        <h3>
          <span>Source Video (English Narration)</span>
          <span class="badge">Original</span>
        </h3>
        <div class="video-wrapper">
          <video id="source-vid" controls preload="metadata" src="/media/source-video"></video>
        </div>
      </div>

      <!-- Dubbed Final Video -->
      <div class="video-col">
        <h3>
          <span>Dubbed Video (<span class="target-lang-name">Spanish</span> Voice + Subs)</span>
          <span class="badge badge-highlight">Final Dubbed</span>
        </h3>
        <div class="video-wrapper">
          <video id="dubbed-vid" controls preload="metadata"></video>
        </div>
      </div>
    </div>
  </section>
</main>

<script>
const LANG_MAP = {"es":"Spanish", "ko":"Korean", "zh":"Chinese (Simplified)", "ja":"Japanese", "hy":"Armenian", "fa":"Farsi (Persian)"};
let currentLang = "es";
let currentStage = 1;
let workflowData = null;

function selectStage(stageNum) {
  currentStage = stageNum;
  document.querySelectorAll('.panel').forEach(p => p.style.display = 'none');
  document.getElementById(`panel-stage-${stageNum}`).style.display = 'block';

  document.querySelectorAll('.step-card').forEach((card, idx) => {
    card.classList.toggle('active', idx + 1 === stageNum);
  });
}

function initLanguages() {
  const container = document.getElementById('lang-buttons');
  container.innerHTML = '';
  Object.entries(LANG_MAP).forEach(([code, name]) => {
    const btn = document.createElement('button');
    btn.className = 'lang-btn' + (code === currentLang ? ' active' : '');
    btn.textContent = name;
    btn.onclick = () => {
      currentLang = code;
      document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b === btn));
      loadWorkflowData();
    };
    container.appendChild(btn);
  });
}

async function loadWorkflowData() {
  const langName = LANG_MAP[currentLang] || currentLang;
  document.querySelectorAll('.target-lang-name').forEach(el => el.textContent = langName);
  document.getElementById('spec-lang-name').textContent = langName;
  document.getElementById('cmd-lang').textContent = currentLang;
  document.getElementById('cmd-lang-out').textContent = currentLang;
  document.getElementById('cmd-lang-file').textContent = currentLang;

  const res = await fetch(`/api/demo-data?lang=${currentLang}`);
  workflowData = await res.json();
  renderStage1();
  renderStage2();
  renderStage3();
  renderStage4();
}

function renderStage1() {
  const tbody = document.getElementById('stage1-tbody');
  tbody.innerHTML = '';
  (workflowData.segments || []).forEach(seg => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="color:#94a3b8; font-weight:600;">${seg.index}</td>
      <td><span class="ts">${seg.orig_start} → ${seg.orig_end}</span></td>
      <td style="color:#334155;">${escapeHtml(seg.original)}</td>
      <td style="color:#0f172a; font-weight:500;">${escapeHtml(seg.translated)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderStage2() {
  const list = document.getElementById('stage2-list');
  list.innerHTML = '';
  (workflowData.segments || []).forEach(seg => {
    const card = document.createElement('div');
    card.className = 'segment-card';
    card.innerHTML = `
      <div class="segment-idx">#${seg.index}</div>
      <div class="segment-body">
        <div class="segment-text">${escapeHtml(seg.translated)}</div>
        <div class="segment-meta">
          <span>Target: ${escapeHtml(seg.original.slice(0, 60))}...</span>
          <span>•</span>
          <span style="font-family:monospace;">${seg.raw_audio_file}</span>
        </div>
      </div>
      <audio controls src="${seg.raw_audio_url}" preload="none"></audio>
    `;
    list.appendChild(card);
  });
}

function renderStage3() {
  const masterAudio = document.getElementById('master-wav-player');
  masterAudio.src = workflowData.assembled_wav_url;

  const tbody = document.getElementById('stage3-tbody');
  tbody.innerHTML = '';
  (workflowData.segments || []).forEach(seg => {
    const tr = document.createElement('tr');
    const origDur = parseTime(seg.orig_end) - parseTime(seg.orig_start);
    const recalcDur = parseTime(seg.recalc_end) - parseTime(seg.recalc_start);
    const delta = recalcDur - origDur;
    let deltaClass = 'delta-zero';
    let deltaText = `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}s`;
    if (delta > 0.05) deltaClass = 'delta-pos';
    else if (delta < -0.05) deltaClass = 'delta-neg';

    tr.innerHTML = `
      <td style="color:#94a3b8; font-weight:600;">${seg.index}</td>
      <td><span class="ts">${seg.orig_start} → ${seg.orig_end}</span> <span style="font-size:11px; color:#64748b;">(${origDur.toFixed(1)}s)</span></td>
      <td><span class="ts-recalc">${seg.recalc_start} → ${seg.recalc_end}</span> <span style="font-size:11px; color:#1d4ed8;">(${recalcDur.toFixed(1)}s)</span></td>
      <td>
        <span class="delta-pill ${deltaClass}">Pacing: ${deltaText}</span>
        <span style="font-size:12px; color:#475569; margin-left:8px;">${escapeHtml(seg.translated)}</span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderStage4() {
  const dubbedVid = document.getElementById('dubbed-vid');
  dubbedVid.src = workflowData.dubbed_video_url;

  // Add embedded subtitle track overlay
  Array.from(dubbedVid.querySelectorAll('track')).forEach(t => t.remove());
  const track = document.createElement('track');
  track.kind = 'subtitles';
  track.label = LANG_MAP[currentLang] || currentLang;
  track.srclang = currentLang;
  track.src = `/media/vtt/${currentLang}`;
  track.default = true;
  dubbedVid.appendChild(track);
}

function parseTime(t) {
  if (!t) return 0;
  const [time, ms] = t.split(',');
  const [h, m, s] = time.split(':').map(Number);
  return h * 3600 + m * 60 + s + Number(ms) / 1000;
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

initLanguages();
loadWorkflowData();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(DEMO_HTML)


@app.route("/api/demo-data")
def api_demo_data():
    from flask import request
    lang = request.args.get("lang", "es")
    if lang not in LANGS:
        lang = "es"

    final_dir = DEMO_MODULE.final_dir
    stem = DEMO_PART.stem

    # Source English captions
    orig_srt_path = CAPTIONS_DIR / final_dir / f"{stem}.srt"
    orig_segments = {s.index: s for s in parse_srt(orig_srt_path)} if orig_srt_path.exists() else {}

    # Translated JSON
    trans_json_path = TRANSLATIONS_DIR / lang / final_dir / f"{stem}.json"
    trans_list = json.loads(trans_json_path.read_text(encoding="utf-8")) if trans_json_path.exists() else []

    # Recalculated SRT
    recalc_srt_path = FINAL_DIR / lang / final_dir / f"{stem}.srt"
    recalc_segments = {s.index: s for s in parse_srt(recalc_srt_path)} if recalc_srt_path.exists() else {}

    combined_segments = []
    for item in trans_list:
        idx = item["index"]
        orig_s = orig_segments.get(idx)
        recalc_s = recalc_segments.get(idx)
        raw_fname = f"{stem}_seg{idx:03d}.mp3"

        combined_segments.append({
            "index": idx,
            "original": item.get("original", orig_s.text if orig_s else ""),
            "translated": item.get("translated", ""),
            "orig_start": orig_s.start if orig_s else item.get("start", ""),
            "orig_end": orig_s.end if orig_s else item.get("end", ""),
            "recalc_start": recalc_s.start if recalc_s else "",
            "recalc_end": recalc_s.end if recalc_s else "",
            "raw_audio_file": raw_fname,
            "raw_audio_url": f"/media/raw-segment/{lang}/{raw_fname}",
        })

    return jsonify({
        "module": DEMO_MODULE_KEY,
        "part_video": DEMO_PART.video,
        "part_stem": stem,
        "lang": lang,
        "segments": combined_segments,
        "assembled_wav_url": f"/media/assembled-audio/{lang}/{stem}.wav",
        "dubbed_video_url": f"/media/dubbed-video/{lang}/{DEMO_PART.out_file(lang)}",
    })


@app.route("/media/source-video")
def serve_source_video():
    """Serves the original English source video."""
    path = DEMO_PART.source_video(BASE_DIR, DEMO_MODULE)
    if not path.exists():
        abort(404, "Source video not found")
    return send_file(str(path), mimetype="video/mp4", conditional=True)


@app.route("/media/raw-segment/<lang>/<filename>")
def serve_raw_segment(lang: str, filename: str):
    """Serves individual segment MP3 audio synthesized by ElevenLabs."""
    path = AUDIO_RAW_DIR / lang / DEMO_MODULE.final_dir / filename
    if not path.exists():
        abort(404, "Segment audio not found")
    return send_file(str(path), mimetype="audio/mpeg", conditional=True)


@app.route("/media/assembled-audio/<lang>/<filename>")
def serve_assembled_audio(lang: str, filename: str):
    """Serves master assembled WAV audio."""
    path = FINAL_DIR / lang / DEMO_MODULE.final_dir / filename
    if not path.exists():
        abort(404, "Assembled audio not found")
    return send_file(str(path), mimetype="audio/wav", conditional=True)


@app.route("/media/dubbed-video/<lang>/<filename>")
def serve_dubbed_video(lang: str, filename: str):
    """Serves the final dubbed and muxed MP4 video."""
    path = OUTPUT_DIR / DEMO_MODULE.out_dir / lang / filename
    if not path.exists():
        abort(404, "Dubbed video not found")
    return send_file(str(path), mimetype="video/mp4", conditional=True)


@app.route("/media/vtt/<lang>")
def serve_vtt_subtitles(lang: str):
    """Generates WebVTT subtitles synchronized with the dubbed audio."""
    srt_path = FINAL_DIR / lang / DEMO_MODULE.final_dir / f"{DEMO_PART.stem}.srt"
    if not srt_path.exists():
        abort(404, "SRT not found")
    srt_text = srt_path.read_text(encoding="utf-8-sig")
    vtt = "WEBVTT\n\n" + re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", srt_text)
    return Response(vtt, mimetype="text/vtt")


def main():
    parser = argparse.ArgumentParser(description="Run Gen-Intro Dubbing Workflow Demo Server")
    parser.add_argument("--port", type=int, default=5050, help="Port to listen on (default: 5050)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address")
    args = parser.parse_args()
    print(f"Starting Gen Intro Workflow Demo at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
