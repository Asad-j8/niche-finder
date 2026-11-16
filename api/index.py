"""
Vercel Serverless Entrypoint for TikTok All-Niche Finder.
Built with Starlette ASGI for 100% Vercel compatibility and fast serverless execution.
Powers an interactive dashboard with all 4 analysis tabs:
  1. Niche Analysis (Opportunity Score, Competition, Demand, Sortable Table, Chart)
  2. Competition Check (Hindi & English case-insensitive search, Low/Med/High badges)
  3. Duplicate Check (0.7*text + 0.3*hashtag formula, threshold 0.6)
  4. Creator Owner Check (profile link, manual verification logger & history)
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

# Ensure project root is in sys.path to import niche_engine
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import niche_engine as engine

# In-memory storage for owner checks during serverless session
SESSION_OWNER_CHECKS: List[Dict[str, str]] = []


def get_sample_df() -> pd.DataFrame:
    """Load the bundled sample dataset."""
    sample_file = ROOT_DIR / "data" / "sample.csv"
    if sample_file.exists():
        return engine.load_videos(str(sample_file))
    return pd.DataFrame(columns=engine.REQUIRED_COLUMNS)


# -------------------------------------------------------------
# API Handlers
# -------------------------------------------------------------
async def api_get_sample(request: Request) -> JSONResponse:
    """Return default dataset statistics and niche list."""
    try:
        df = get_sample_df()
        niches = sorted(df["niche"].unique().tolist())
        summary = {
            "total_videos": len(df),
            "unique_niches": int(df["niche"].nunique()),
            "unique_creators": int(df["creator"].nunique()),
            "total_views": int(df["views"].sum()),
            "niches": niches,
        }
        return JSONResponse({"status": "success", "summary": summary})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def api_score_niches(request: Request) -> JSONResponse:
    """Compute niche opportunity scoring with optional filtering."""
    try:
        body = await request.json()
        selected_niches = body.get("selected_niches", [])
        csv_text = body.get("csv_text")

        if csv_text:
            df = engine.load_videos(io.StringIO(csv_text))
        else:
            df = get_sample_df()

        scores = engine.score_niches(df, selected_niches=selected_niches or None)
        return JSONResponse({
            "status": "success",
            "data": scores.to_dict(orient="records"),
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


async def api_competition_check(request: Request) -> JSONResponse:
    """Perform competition search across caption and hashtags."""
    try:
        body = await request.json()
        keyword = body.get("keyword", "")
        csv_text = body.get("csv_text")

        if csv_text:
            df = engine.load_videos(io.StringIO(csv_text))
        else:
            df = get_sample_df()

        result = engine.competition_check(df, keyword)
        return JSONResponse({
            "status": "success",
            "matching_videos_count": result["matching_videos_count"],
            "unique_creators_count": result["unique_creators_count"],
            "competition_label": result["competition_label"],
            "top_videos": result["top_videos"].to_dict(orient="records"),
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


async def api_duplicate_check(request: Request) -> JSONResponse:
    """Perform duplicate idea check with text similarity + hashtag overlap."""
    try:
        body = await request.json()
        query = body.get("query", "")
        csv_text = body.get("csv_text")

        if csv_text:
            df = engine.load_videos(io.StringIO(csv_text))
        else:
            df = get_sample_df()

        matches = engine.duplicate_check(df, query)
        return JSONResponse({
            "status": "success",
            "matches": matches.to_dict(orient="records"),
            "count": len(matches),
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


async def api_save_owner_check(request: Request) -> JSONResponse:
    """Save manual owner check record."""
    try:
        body = await request.json()
        username = body.get("username", "")
        status = body.get("status", "Unsure")
        note = body.get("note", "")

        # Try saving to disk if writable, also keep in session
        try:
            record = engine.save_owner_check(username, status, note)
        except Exception:
            from datetime import datetime
            clean_user = username.strip().lstrip("@")
            record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "username": clean_user,
                "profile_url": f"https://www.tiktok.com/@{clean_user}",
                "status": status,
                "note": note,
            }
        SESSION_OWNER_CHECKS.insert(0, record)
        return JSONResponse({"status": "success", "record": record})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


async def api_load_owner_checks(request: Request) -> JSONResponse:
    """Retrieve history of manual owner checks."""
    try:
        history_df = engine.load_owner_checks()
        disk_records = history_df.to_dict(orient="records") if not history_df.empty else []
        # Merge session checks avoiding duplicates
        all_records = SESSION_OWNER_CHECKS + [r for r in disk_records if r not in SESSION_OWNER_CHECKS]
        return JSONResponse({"status": "success", "history": all_records})
    except Exception as e:
        return JSONResponse({"status": "success", "history": SESSION_OWNER_CHECKS})


# -------------------------------------------------------------
# Frontend HTML Dashboard
# -------------------------------------------------------------
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TikTok All-Niche Finder</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { background-color: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .navbar { background: linear-gradient(135deg, #FF0050 0%, #00F2FE 100%); }
    .nav-tabs .nav-link { color: #495057; font-weight: 500; font-size: 1.05rem; }
    .nav-tabs .nav-link.active { font-weight: 700; color: #FF0050; border-bottom: 3px solid #FF0050; }
    .card { border-radius: 12px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
    .badge-low { background-color: #d4edda; color: #155724; padding: 6px 14px; border-radius: 6px; font-weight: 700; }
    .badge-medium { background-color: #fff3cd; color: #856404; padding: 6px 14px; border-radius: 6px; font-weight: 700; }
    .badge-high { background-color: #f8d7da; color: #721c24; padding: 6px 14px; border-radius: 6px; font-weight: 700; }
    .stat-card { border-left: 4px solid #FF0050; }
    .table th { background-color: #f1f3f5; }
    .clickable-url { color: #0d6efd; text-decoration: none; font-weight: 500; }
    .clickable-url:hover { text-decoration: underline; }
  </style>
</head>
<body>

  <!-- Navbar -->
  <nav class="navbar navbar-dark shadow-sm py-3 mb-4">
    <div class="container">
      <span class="navbar-brand mb-0 h1 fw-bold fs-3">🎯 TikTok All-Niche Finder</span>
      <span class="badge bg-dark bg-opacity-50 text-white px-3 py-2">100% Offline & Free</span>
    </div>
  </nav>

  <div class="container mb-5">
    
    <!-- Dataset Control Bar -->
    <div class="card p-3 mb-4">
      <div class="row align-items-center">
        <div class="col-md-7">
          <label class="form-label fw-bold mb-1">📁 Upload Custom TikTok CSV:</label>
          <input type="file" id="csvFileInput" class="form-control" accept=".csv" onchange="handleFileUpload(event)">
          <small class="text-muted">Required columns: niche, hashtag, caption, creator, views, likes, video_url</small>
        </div>
        <div class="col-md-5 text-md-end mt-3 mt-md-0">
          <span id="datasetBadge" class="badge bg-primary p-2 fs-6">Loaded: data/sample.csv (35 videos)</span>
          <button class="btn btn-outline-secondary btn-sm ms-2" onclick="resetToSample()">Reset Sample</button>
        </div>
      </div>
      <div id="uploadError" class="alert alert-danger mt-3 d-none"></div>
    </div>

    <!-- Overview Metrics -->
    <div class="row g-3 mb-4">
      <div class="col-6 col-md-3">
        <div class="card p-3 stat-card">
          <div class="text-muted small fw-bold">TOTAL VIDEOS</div>
          <div class="fs-4 fw-bold" id="statVideos">35</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card p-3 stat-card" style="border-left-color: #00F2FE;">
          <div class="text-muted small fw-bold">UNIQUE NICHES</div>
          <div class="fs-4 fw-bold" id="statNiches">5</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card p-3 stat-card" style="border-left-color: #28a745;">
          <div class="text-muted small fw-bold">UNIQUE CREATORS</div>
          <div class="fs-4 fw-bold" id="statCreators">-</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card p-3 stat-card" style="border-left-color: #ffc107;">
          <div class="text-muted small fw-bold">TOTAL VIEWS</div>
          <div class="fs-4 fw-bold" id="statViews">-</div>
        </div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <ul class="nav nav-tabs mb-4" id="mainTabs" role="tablist">
      <li class="nav-item">
        <button class="nav-link active" id="niche-tab" data-bs-toggle="tab" data-bs-target="#nichePane">📊 Niche Analysis</button>
      </li>
      <li class="nav-item">
        <button class="nav-link" id="comp-tab" data-bs-toggle="tab" data-bs-target="#compPane">🔍 Competition Check</button>
      </li>
      <li class="nav-item">
        <button class="nav-link" id="dup-tab" data-bs-toggle="tab" data-bs-target="#dupPane">⚡ Duplicate Check</button>
      </li>
      <li class="nav-item">
        <button class="nav-link" id="owner-tab" data-bs-toggle="tab" data-bs-target="#ownerPane">👤 Owner Check</button>
      </li>
    </ul>

    <div class="tab-content">

      <!-- TAB 1: NICHE ANALYSIS -->
      <div class="tab-pane fade show active" id="nichePane">
        <div class="card p-4">
          <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap">
            <h5 class="fw-bold mb-0">Niche Performance & Opportunity Scoring</h5>
            <small class="text-muted">Opportunity Score = Demand × (1 - Competition) × 100</small>
          </div>

          <!-- Niche Multiselect Filter -->
          <div class="mb-4">
            <label class="form-label fw-bold small text-muted">Filter Niches:</label>
            <div id="nicheCheckboxes" class="d-flex flex-wrap gap-2"></div>
          </div>

          <!-- Bar Chart -->
          <div class="mb-4 p-3 bg-light rounded" style="max-height: 340px;">
            <canvas id="nicheChart" height="90"></canvas>
          </div>

          <!-- Sortable Table -->
          <div class="table-responsive">
            <table class="table table-hover align-middle" id="nicheTable">
              <thead>
                <tr>
                  <th>Niche</th>
                  <th>Videos</th>
                  <th>Creators</th>
                  <th>Avg Views</th>
                  <th>Median Views</th>
                  <th>Top Views</th>
                  <th>Competition (0-1)</th>
                  <th>Demand (0-1)</th>
                  <th class="text-end">Opportunity Score</th>
                </tr>
              </thead>
              <tbody id="nicheTableBody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- TAB 2: COMPETITION CHECK -->
      <div class="tab-pane fade" id="compPane">
        <div class="card p-4">
          <h5 class="fw-bold mb-2">Topic / Keyword Competition Check</h5>
          <p class="text-muted">Search across captions and hashtags (Hindi Devanagari & English supported).</p>

          <div class="input-group mb-4">
            <input type="text" id="compKeyword" class="form-control form-control-lg" placeholder="Type keyword (e.g. fitness, पनीर, budget, travel, शादी)...">
            <button class="btn btn-primary px-4 fw-bold" onclick="runCompetitionCheck()">Check Competition</button>
          </div>

          <!-- Competition Result Card -->
          <div id="compResultBox" class="d-none">
            <div class="row g-3 mb-4">
              <div class="col-md-4">
                <div class="p-3 bg-light rounded text-center">
                  <div class="text-muted small">MATCHING VIDEOS</div>
                  <div class="fs-3 fw-bold" id="compMatchesCount">0</div>
                </div>
              </div>
              <div class="col-md-4">
                <div class="p-3 bg-light rounded text-center">
                  <div class="text-muted small">UNIQUE CREATORS</div>
                  <div class="fs-3 fw-bold" id="compCreatorsCount">0</div>
                </div>
              </div>
              <div class="col-md-4">
                <div class="p-3 bg-light rounded text-center">
                  <div class="text-muted small mb-1">COMPETITION LEVEL</div>
                  <span id="compBadge" class="badge-low fs-5">Low</span>
                </div>
              </div>
            </div>

            <h6 class="fw-bold mb-3">Top 10 Matching Videos by Views</h6>
            <div class="table-responsive">
              <table class="table table-hover">
                <thead>
                  <tr>
                    <th>Creator</th>
                    <th>Niche</th>
                    <th>Views</th>
                    <th>Likes</th>
                    <th>Caption</th>
                    <th>Video Link</th>
                  </tr>
                </thead>
                <tbody id="compTableBody"></tbody>
              </table>
            </div>
          </div>
          <div id="compEmptyMsg" class="alert alert-info d-none">No matching videos found for this keyword.</div>
        </div>
      </div>

      <!-- TAB 3: DUPLICATE CHECK -->
      <div class="tab-pane fade" id="dupPane">
        <div class="card p-4">
          <h5 class="fw-bold mb-2">Duplicate Idea & Caption Check</h5>
          <p class="text-muted">
            Formula: <code>Final Score = 0.7 × Text Similarity + 0.3 × Hashtag Overlap</code>.<br>
            Displays matches with score ≥ 0.60. Supports Hindi (Devanagari) and English text.
          </p>
          <div class="alert alert-info py-2 small">ℹ️ Note: This check only analyzes the uploaded CSV dataset, not all of TikTok.</div>

          <div class="mb-3">
            <textarea id="dupQuery" class="form-control" rows="3" placeholder="Paste your video caption or idea here... (e.g. वजन घटाने के 5 आसान घरेलू उपाय #fitness)"></textarea>
          </div>
          <button class="btn btn-primary fw-bold px-4" onclick="runDuplicateCheck()">Check for Duplicates</button>

          <div id="dupResultBox" class="mt-4 d-none">
            <div id="dupStatusAlert" class="alert"></div>
            <div class="table-responsive">
              <table class="table table-hover" id="dupTable">
                <thead>
                  <tr>
                    <th>Creator</th>
                    <th>Match Score</th>
                    <th>Text Similarity</th>
                    <th>Hashtag Overlap</th>
                    <th>Caption</th>
                    <th>Video Link</th>
                  </tr>
                </thead>
                <tbody id="dupTableBody"></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 4: OWNER CHECK -->
      <div class="tab-pane fade" id="ownerPane">
        <div class="card p-4">
          <h5 class="fw-bold mb-2">Creator Owner Check</h5>
          <p class="text-muted">Look up a TikTok profile link and manually log verification notes without scraping.</p>

          <div class="row g-3 mb-4">
            <div class="col-md-8">
              <label class="form-label fw-bold">TikTok Username:</label>
              <input type="text" id="ownerUsername" class="form-control" placeholder="e.g. fit_rahul or @fit_rahul">
            </div>
            <div class="col-md-4 d-flex align-items-end">
              <button class="btn btn-outline-primary w-100 fw-bold" onclick="generateProfileLink()">Generate Link</button>
            </div>
          </div>

          <div id="ownerProfileBox" class="alert alert-light border p-3 mb-4 d-none">
            <span class="fw-bold">🔗 Profile URL:</span> 
            <a id="ownerProfileLink" href="#" target="_blank" class="clickable-url ms-2"></a>
          </div>

          <!-- Form to save manual check -->
          <div class="card bg-light p-3 mb-4">
            <h6 class="fw-bold mb-3">Record Manual Verification</h6>
            <div class="row g-3">
              <div class="col-md-4">
                <label class="form-label small fw-bold">Status:</label>
                <select id="ownerStatus" class="form-select">
                  <option value="Found">Found</option>
                  <option value="Not found">Not found</option>
                  <option value="Unsure">Unsure</option>
                </select>
              </div>
              <div class="col-md-6">
                <label class="form-label small fw-bold">Notes / Remarks:</label>
                <input type="text" id="ownerNote" class="form-control" placeholder="e.g. Active creator in fitness niche">
              </div>
              <div class="col-md-2 d-flex align-items-end">
                <button class="btn btn-success w-100 fw-bold" onclick="saveOwnerCheck()">Save</button>
              </div>
            </div>
          </div>

          <!-- Saved History -->
          <h6 class="fw-bold mb-3">📜 Manual Verification History</h6>
          <div class="table-responsive">
            <table class="table table-hover">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Username</th>
                  <th>Status</th>
                  <th>Notes</th>
                  <th>Profile Link</th>
                </tr>
              </thead>
              <tbody id="ownerHistoryBody"></tbody>
            </table>
          </div>
        </div>
      </div>

    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  <script>
    let currentCsvText = null;
    let allNiches = [];
    let selectedNiches = [];
    let chartInstance = null;

    // Initialize on page load
    document.addEventListener("DOMContentLoaded", () => {
      loadSampleSummary();
      loadOwnerChecks();
    });

    async function loadSampleSummary() {
      try {
        const res = await fetch("/api/sample");
        const json = await res.json();
        if (json.status === "success") {
          updateStats(json.summary);
          allNiches = json.summary.niches;
          selectedNiches = [...allNiches];
          renderNicheCheckboxes();
          loadNicheScores();
        }
      } catch (err) {
        console.error("Error loading sample:", err);
      }
    }

    function updateStats(summary) {
      document.getElementById("statVideos").innerText = Number(summary.total_videos).toLocaleString();
      document.getElementById("statNiches").innerText = summary.unique_niches;
      document.getElementById("statCreators").innerText = summary.unique_creators;
      document.getElementById("statViews").innerText = Number(summary.total_views).toLocaleString();
    }

    function renderNicheCheckboxes() {
      const container = document.getElementById("nicheCheckboxes");
      container.innerHTML = "";
      allNiches.forEach(n => {
        const div = document.createElement("div");
        div.className = "form-check form-check-inline";
        div.innerHTML = `
          <input class="form-check-input" type="checkbox" id="chk_${n}" value="${n}" checked onchange="handleNicheFilterChange()">
          <label class="form-check-label text-capitalize" for="chk_${n}">${n}</label>
        `;
        container.appendChild(div);
      });
    }

    function handleNicheFilterChange() {
      selectedNiches = [];
      allNiches.forEach(n => {
        const el = document.getElementById(`chk_${n}`);
        if (el && el.checked) selectedNiches.push(n);
      });
      loadNicheScores();
    }

    async function loadNicheScores() {
      try {
        const res = await fetch("/api/score_niches", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ csv_text: currentCsvText, selected_niches: selectedNiches })
        });
        const json = await res.json();
        if (json.status === "success") {
          renderNicheTable(json.data);
          renderChart(json.data);
        }
      } catch (err) {
        console.error(err);
      }
    }

    function renderNicheTable(data) {
      const tbody = document.getElementById("nicheTableBody");
      tbody.innerHTML = "";
      if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No data for selected niches.</td></tr>';
        return;
      }
      data.forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="fw-bold text-capitalize">${r.niche}</td>
          <td>${r.video_count}</td>
          <td>${r.unique_creators}</td>
          <td>${Number(r.avg_views).toLocaleString()}</td>
          <td>${Number(r.median_views).toLocaleString()}</td>
          <td>${Number(r.top_views).toLocaleString()}</td>
          <td>${(r.competition * 100).toFixed(0)}%</td>
          <td>${(r.demand * 100).toFixed(0)}%</td>
          <td class="text-end fw-bold fs-6 text-primary">${r.opportunity_score}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function renderChart(data) {
      const ctx = document.getElementById("nicheChart").getContext("2d");
      const labels = data.map(d => d.niche.toUpperCase());
      const scores = data.map(d => d.opportunity_score);

      if (chartInstance) chartInstance.destroy();
      chartInstance = new Chart(ctx, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [{
            label: "Opportunity Score (0-100)",
            data: scores,
            backgroundColor: "rgba(255, 0, 80, 0.7)",
            borderColor: "rgba(255, 0, 80, 1)",
            borderWidth: 1,
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { y: { beginAtZero: true, max: 100 } }
        }
      });
    }

    // CSV File Upload
    function handleFileUpload(evt) {
      const file = evt.target.files[0];
      const errEl = document.getElementById("uploadError");
      errEl.classList.add("d-none");
      if (!file) return;

      const reader = new FileReader();
      reader.onload = async (e) => {
        currentCsvText = e.target.result;
        // Verify required columns in header
        const required = ["niche", "hashtag", "caption", "creator", "views", "likes", "video_url"];
        const firstLine = currentCsvText.split("\\n")[0].toLowerCase();
        const missing = required.filter(col => !firstLine.includes(col));

        if (missing.length > 0) {
          errEl.innerText = "Error: Missing required columns: " + missing.join(", ");
          errEl.classList.remove("d-none");
          return;
        }

        document.getElementById("datasetBadge").innerText = "Uploaded: " + file.name;
        document.getElementById("datasetBadge").className = "badge bg-success p-2 fs-6";

        // Refresh scores and niche filter
        const res = await fetch("/api/score_niches", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ csv_text: currentCsvText })
        });
        const json = await res.json();
        if (json.status === "success" && json.data) {
          allNiches = json.data.map(d => d.niche);
          selectedNiches = [...allNiches];
          renderNicheCheckboxes();
          renderNicheTable(json.data);
          renderChart(json.data);

          // Update metrics
          const totalV = json.data.reduce((a, b) => a + b.video_count, 0);
          document.getElementById("statVideos").innerText = totalV;
          document.getElementById("statNiches").innerText = json.data.length;
        }
      };
      reader.readAsText(file);
    }

    function resetToSample() {
      currentCsvText = null;
      document.getElementById("csvFileInput").value = "";
      document.getElementById("uploadError").classList.add("d-none");
      document.getElementById("datasetBadge").innerText = "Loaded: data/sample.csv (35 videos)";
      document.getElementById("datasetBadge").className = "badge bg-primary p-2 fs-6";
      loadSampleSummary();
    }

    // Competition Check
    async function runCompetitionCheck() {
      const kw = document.getElementById("compKeyword").value.trim();
      const resBox = document.getElementById("compResultBox");
      const emptyMsg = document.getElementById("compEmptyMsg");
      if (!kw) return;

      const res = await fetch("/api/competition_check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: kw, csv_text: currentCsvText })
      });
      const json = await res.json();
      if (json.status === "success") {
        if (json.matching_videos_count === 0) {
          resBox.classList.add("d-none");
          emptyMsg.classList.remove("d-none");
          return;
        }
        emptyMsg.classList.add("d-none");
        resBox.classList.remove("d-none");

        document.getElementById("compMatchesCount").innerText = json.matching_videos_count;
        document.getElementById("compCreatorsCount").innerText = json.unique_creators_count;
        
        const badge = document.getElementById("compBadge");
        badge.innerText = json.competition_label;
        badge.className = "badge-" + json.competition_label.toLowerCase() + " fs-5";

        const tbody = document.getElementById("compTableBody");
        tbody.innerHTML = "";
        json.top_videos.forEach(v => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td class="fw-bold">@${v.creator}</td>
            <td class="text-capitalize">${v.niche}</td>
            <td>${Number(v.views).toLocaleString()}</td>
            <td>${Number(v.likes).toLocaleString()}</td>
            <td class="small">${v.caption}</td>
            <td><a href="${v.video_url}" target="_blank" class="clickable-url">Open Video 🔗</a></td>
          `;
          tbody.appendChild(tr);
        });
      }
    }

    // Duplicate Check
    async function runDuplicateCheck() {
      const q = document.getElementById("dupQuery").value.trim();
      const resBox = document.getElementById("dupResultBox");
      const alertEl = document.getElementById("dupStatusAlert");
      const tbody = document.getElementById("dupTableBody");
      if (!q) return;

      const res = await fetch("/api/duplicate_check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, csv_text: currentCsvText })
      });
      const json = await res.json();
      resBox.classList.remove("d-none");
      tbody.innerHTML = "";

      if (json.count === 0) {
        alertEl.className = "alert alert-success fw-bold";
        alertEl.innerText = "Is data mein koi milta-julta content nahi mila.";
        document.getElementById("dupTable").classList.add("d-none");
      } else {
        alertEl.className = "alert alert-warning fw-bold";
        alertEl.innerText = `Found ${json.count} similar idea(s) in this dataset with score ≥ 0.60:`;
        document.getElementById("dupTable").classList.remove("d-none");

        json.matches.forEach(m => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td class="fw-bold">@${m.creator}</td>
            <td class="fw-bold text-primary">${m.score.toFixed(3)}</td>
            <td>${m.text_similarity.toFixed(3)}</td>
            <td>${m.hashtag_overlap.toFixed(3)}</td>
            <td class="small">${m.caption}</td>
            <td><a href="${m.video_url}" target="_blank" class="clickable-url">Open Video 🔗</a></td>
          `;
          tbody.appendChild(tr);
        });
      }
    }

    // Owner Check
    function generateProfileLink() {
      const username = document.getElementById("ownerUsername").value.trim().replace(/^@/, "");
      const box = document.getElementById("ownerProfileBox");
      const link = document.getElementById("ownerProfileLink");
      if (!username) return;

      const url = `https://www.tiktok.com/@${username}`;
      link.href = url;
      link.innerText = url;
      box.classList.remove("d-none");
    }

    async function saveOwnerCheck() {
      const username = document.getElementById("ownerUsername").value.trim().replace(/^@/, "");
      const status = document.getElementById("ownerStatus").value;
      const note = document.getElementById("ownerNote").value.trim();
      if (!username) return alert("Please enter a username.");

      await fetch("/api/owner_check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, status, note })
      });
      document.getElementById("ownerNote").value = "";
      loadOwnerChecks();
    }

    async function loadOwnerChecks() {
      try {
        const res = await fetch("/api/owner_checks");
        const json = await res.json();
        const tbody = document.getElementById("ownerHistoryBody");
        tbody.innerHTML = "";
        if (!json.history || json.history.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No manual checks logged yet.</td></tr>';
          return;
        }
        json.history.forEach(r => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td class="small">${r.timestamp}</td>
            <td class="fw-bold">@${r.username}</td>
            <td><span class="badge bg-secondary">${r.status}</span></td>
            <td>${r.note || "-"}</td>
            <td><a href="${r.profile_url}" target="_blank" class="clickable-url">Profile 🔗</a></td>
          `;
          tbody.appendChild(tr);
        });
      } catch (err) {
        console.error(err);
      }
    }
  </script>
</body>
</html>
"""

async def homepage(request: Request) -> HTMLResponse:
    """Serve the single-page dashboard."""
    return HTMLResponse(HTML_CONTENT)


# Starlette routes
routes = [
    Route("/", homepage),
    Route("/api/sample", api_get_sample, methods=["GET"]),
    Route("/api/score_niches", api_score_niches, methods=["POST"]),
    Route("/api/competition_check", api_competition_check, methods=["POST"]),
    Route("/api/duplicate_check", api_duplicate_check, methods=["POST"]),
    Route("/api/owner_check", api_save_owner_check, methods=["POST"]),
    Route("/api/owner_checks", api_load_owner_checks, methods=["GET"]),
]

app = Starlette(debug=False, routes=routes)
