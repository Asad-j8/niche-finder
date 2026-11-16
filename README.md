# 🎯 TikTok All-Niche Finder

[![Streamlit](https://img.shields.io/badge/Streamlit-1.67+-FF4B4B.svg)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Pytest%20Passing-brightgreen.svg)]()
[![Offline](https://img.shields.io/badge/100%25-Offline%20Analysis-success.svg)]()

A free, open-source Streamlit web application for discovering high-potential TikTok niches, analyzing creator competition, detecting duplicate content ideas, and maintaining manual creator verification logs.

> [!IMPORTANT]
> **Privacy & Offline Guarantee**: This tool never scrapes TikTok web pages, apps, or internal APIs. All analysis runs completely offline and locally against CSV data that you provide.

---

## 🌟 Key Features

### 1. 📊 Niche Analysis & Opportunity Scoring (Tab "Niche Analysis")
Analyzes every niche across your dataset:
- Metrics: `video_count`, `unique_creators`, `avg_views`, `median_views`, `top_views`
- Normalized Competition: $\text{Competition} = \frac{\text{unique\_creators}}{\max(\text{unique\_creators})}$ (range 0 to 1)
- Normalized Demand: $\text{Demand} = \frac{\text{avg\_views}}{\max(\text{avg\_views})}$ (range 0 to 1)
- **Opportunity Score**:
  $$\text{Opportunity Score} = \text{Demand} \times (1 - \text{Competition}) \times 100$$
- Interactive sortable data table and visual bar charts.
- Multiselect filter to compare specific niches.

### 2. 🔍 Topic & Keyword Competition Check (Tab "Competition Check")
- Case-insensitive search across video captions and hashtags supporting both **English** and **Hindi (Devanagari)**.
- Metrics calculated:
  - Matching video count
  - Number of unique creators
  - Competition label:
    - **Low**: under 5 creators
    - **Medium**: 5 to 15 creators
    - **High**: over 15 creators
- Top 10 matching videos ranked by view count with direct, clickable video links.

### 3. ⚡ Duplicate Idea Detection (Tab "Duplicate Check")
- Paste an idea or caption to test against existing videos in your dataset.
- Text normalization: Converts to lowercase, strips hashtags and punctuation, while preserving `a-z`, `0-9`, and Devanagari (`\u0900-\u097F`).
- Similarity calculation:
  $$\text{Final Score} = 0.7 \times \text{Text Similarity} + 0.3 \times \text{Hashtag Overlap}$$
  - Text similarity uses `difflib.SequenceMatcher`.
  - Hashtag overlap uses Jaccard similarity.
- Displays matches with $\text{score} \ge 0.60$ sorted by relevance.
- If no match is found, clearly displays: *"Is data mein koi milta-julta content nahi mila."*

### 4. 👤 Creator Owner Check (Tab "Owner Check")
- Enter any TikTok handle (with or without `@`).
- Direct link to profile: `https://www.tiktok.com/@{username}`.
- Manual logging form for verification status (`Found`, `Not found`, `Unsure`) and notes.
- Saves results to local CSV file `owner_checks.csv` (git-ignored) with timestamped history.

---

## 📁 Input CSV Format

The application expects a CSV file encoded in `utf-8-sig` (ensuring full support for Devanagari Hindi text and emojis).

### Required Columns:
| Column | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `niche` | string | Category or niche name | `fitness`, `cooking`, `finance` |
| `hashtag` | string | Hashtags associated with the video | `#fitness #workout #gym` |
| `caption` | string | Full video caption (Hindi or English) | `वजन घटाने के 5 आसान घरेलू उपाय` |
| `creator` | string | TikTok handle / creator username | `fit_rahul` |
| `views` | integer | Number of views (invalid values become 0) | `152000` |
| `likes` | integer | Number of likes (invalid values become 0) | `12400` |
| `video_url` | string | Web link to the TikTok video | `https://www.tiktok.com/@fit_rahul/video/7001001` |

### Raw CSV Example:
```csv
niche,hashtag,caption,creator,views,likes,video_url
fitness,#fitness #fatloss,वजन घटाने के 5 आसान घरेलू उपाय,fit_rahul,152000,12400,https://www.tiktok.com/@fit_rahul/video/7001001
cooking,#cooking #paneer,घर पर बनाएं रेस्टोरेंट जैसी पनीर बटर मसाला,chef_amit,420000,38000,https://www.tiktok.com/@chef_amit/video/7002001
finance,#finance #investing,महीने के 5000 रुपये कैसे बचाएं और निवेश करें,fin_guru,510000,42000,https://www.tiktok.com/@fin_guru/video/7003001
```

A bundled sample dataset with 35 curated records is located at `data/sample.csv`.

---

## 🚀 Local Run Steps

### 1. Clone Repository
```bash
git clone https://github.com/Asad-j8/niche-finder.git
cd niche-finder
```

### 2. Set Up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Application
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 🌐 Linux Virtual Server Deployment (VPS / Ubuntu / Debian)

Follow these steps to deploy on a Linux virtual server:

```bash
# 1. Clone repository
git clone https://github.com/Asad-j8/niche-finder.git
cd niche-finder

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install requirements
pip install -r requirements.txt

# 4. Run Streamlit bound to all interfaces
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### 🔄 Optional: Keep Running After Reboot with systemd

To keep the application running continuously in the background and survive server reboots:

1. Create a systemd service file:
```bash
sudo nano /etc/systemd/system/tiktok-niche-finder.service
```

2. Paste the following configuration (replace `your_user` and paths with your server's actual user and directory):
```ini
[Unit]
Description=TikTok All-Niche Finder Streamlit App
After=network.target

[Service]
User=your_user
WorkingDirectory=/home/your_user/niche-finder
ExecStart=/home/your_user/niche-finder/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tiktok-niche-finder
sudo systemctl start tiktok-niche-finder
sudo systemctl status tiktok-niche-finder
```

Your app will now be accessible at `http://<your-server-ip>:8501`.

---

## 🧪 Running Unit Tests

Run the test suite using `pytest`:
```bash
pytest -v
```
All 9 unit and integration tests verify:
- Missing required columns error validation
- Numeric coercion and cleaning for views and likes
- Text and Devanagari normalization
- Niche opportunity scoring calculation and descending ordering
- Creator competition threshold classification (Low, Medium, High)
- Case-insensitive Hindi and English search
- Duplicate detection on Hindi captions with $\ge 0.6$ score threshold
- Manual owner check logging and persistence

---

## 📂 Project Structure

```
niche-finder/
├── app.py               # Streamlit web application & interactive UI
├── niche_engine.py      # Pure logic engine (scoring, search, similarity, storage)
├── requirements.txt     # Python dependencies (streamlit, pandas, pytest)
├── pytest.ini           # Pytest configuration
├── README.md            # Documentation and deployment guides
├── .gitignore           # Git ignore rules
├── data/
│   └── sample.csv       # Sample dataset with 35 videos across 5 niches
└── tests/
    └── test_engine.py   # Complete pytest test suite
```

---

## 📜 License
This project is open-source under the [MIT License](LICENSE).
