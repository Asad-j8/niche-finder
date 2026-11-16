"""
Unit and integration tests for niche_engine.py.
Covers:
- Missing columns validation error
- score_niches calculations, column schema, and opportunity_score ordering
- competition labels (Low, Medium, High) and thresholds
- duplicate detection including Hindi caption matching
- normalize_text for English and Devanagari (Hindi)
- owner check save and load
"""

import io
import os
import sys
from pathlib import Path
import pandas as pd
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import niche_engine as engine


@pytest.fixture
def sample_csv_path():
    """Path to the bundled sample dataset."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "data", "sample.csv")


@pytest.fixture
def sample_df(sample_csv_path):
    """Loaded sample DataFrame."""
    return engine.load_videos(sample_csv_path)


def test_missing_columns_error():
    """Verify load_videos raises ValueError with missing column names."""
    invalid_csv = io.StringIO(
        "niche,hashtag,caption,creator\n"
        "fitness,#gym,Workout video,fit_alex\n"
    )
    with pytest.raises(ValueError) as excinfo:
        engine.load_videos(invalid_csv)

    err_msg = str(excinfo.value)
    assert "Missing required columns" in err_msg
    assert "views" in err_msg
    assert "likes" in err_msg
    assert "video_url" in err_msg


def test_load_videos_numeric_cleaning():
    """Verify views and likes are parsed to numbers, and bad/missing values become 0."""
    csv_data = io.StringIO(
        "niche,hashtag,caption,creator,views,likes,video_url\n"
        "fitness,#fit,Test caption 1,user1,1000,50,https://example.com/1\n"
        "cooking,#cook,Test caption 2,user2,invalid,NaN,https://example.com/2\n"
        "finance,#money,Test caption 3,user3,-50,abc,https://example.com/3\n"
    )
    df = engine.load_videos(csv_data)
    assert len(df) == 3
    assert df.loc[0, "views"] == 1000
    assert df.loc[0, "likes"] == 50
    # Invalid values coerced to 0
    assert df.loc[1, "views"] == 0
    assert df.loc[1, "likes"] == 0
    # Negative clipped to 0
    assert df.loc[2, "views"] == 0
    assert df.loc[2, "likes"] == 0


def test_normalize_text():
    """Verify text normalization removes hashtags, punctuation, and preserves a-z, 0-9, and Devanagari."""
    # English normalization
    raw_en = "Top 3 Chest Workouts for Massive Muscle in 2026! #fitness #gym"
    norm_en = engine.normalize_text(raw_en)
    assert norm_en == "top 3 chest workouts for massive muscle in 2026"

    # Hindi normalization with punctuation and hashtags
    raw_hi = "वजन घटाने के 5 आसान घरेलू उपाय! रोज सुबह करें। #fitness #वेटलॉस"
    norm_hi = engine.normalize_text(raw_hi)
    assert norm_hi == "वजन घटाने के 5 आसान घरेलू उपाय रोज सुबह करें"

    # Edge cases
    assert engine.normalize_text("") == ""
    assert engine.normalize_text(None) == ""
    assert engine.normalize_text("   ###   ") == ""


def test_score_niches_output_and_ordering(sample_df):
    """Verify score_niches computes correct fields and orders descending by opportunity_score."""
    score_df = engine.score_niches(sample_df)

    expected_cols = [
        "niche",
        "video_count",
        "unique_creators",
        "avg_views",
        "median_views",
        "top_views",
        "competition",
        "demand",
        "opportunity_score",
    ]
    for col in expected_cols:
        assert col in score_df.columns

    # Verify 5 distinct niches from sample data
    assert len(score_df) == 5
    assert set(score_df["niche"]) == {"fitness", "cooking", "finance", "travel", "comedy"}

    # Verify descending sort by opportunity_score
    scores = score_df["opportunity_score"].tolist()
    assert scores == sorted(scores, reverse=True)

    # Opportunity scores must be between 0 and 100
    for score in scores:
        assert 0.0 <= score <= 100.0

    # Competition and demand must be between 0.0 and 1.0
    for val in score_df["competition"]:
        assert 0.0 <= val <= 1.0
    for val in score_df["demand"]:
        assert 0.0 <= val <= 1.0

    # Test filtering by selected_niches
    filtered_score = engine.score_niches(sample_df, selected_niches=["fitness", "cooking"])
    assert len(filtered_score) == 2
    assert set(filtered_score["niche"]) == {"fitness", "cooking"}


def test_competition_labels():
    """Verify competition labels Low, Medium, and High based on unique creator thresholds."""
    # Synthetic data for threshold boundary verification
    rows = []
    # 3 creators -> Low (< 5)
    for i in range(3):
        rows.append({
            "niche": "tech",
            "hashtag": "#tech #gadgets",
            "caption": "Latest gadget review",
            "creator": f"creator_low_{i}",
            "views": 1000 + i,
            "likes": 50,
            "video_url": f"https://example.com/v_{i}",
        })
    df_low = pd.DataFrame(rows)
    res_low = engine.competition_check(df_low, "gadget")
    assert res_low["matching_videos_count"] == 3
    assert res_low["unique_creators_count"] == 3
    assert res_low["competition_label"] == "Low"

    # 10 creators -> Medium (5 to 15)
    rows_med = []
    for i in range(10):
        rows_med.append({
            "niche": "tech",
            "hashtag": "#ai #tools",
            "caption": "AI tools you need",
            "creator": f"creator_med_{i}",
            "views": 2000 + i,
            "likes": 100,
            "video_url": f"https://example.com/v_{i}",
        })
    df_med = pd.DataFrame(rows_med)
    res_med = engine.competition_check(df_med, "ai tools")
    assert res_med["unique_creators_count"] == 10
    assert res_med["competition_label"] == "Medium"

    # 16 creators -> High (> 15)
    rows_high = []
    for i in range(16):
        rows_high.append({
            "niche": "tech",
            "hashtag": "#coding #python",
            "caption": "Learn Python in 60s",
            "creator": f"creator_high_{i}",
            "views": 3000 + i,
            "likes": 200,
            "video_url": f"https://example.com/v_{i}",
        })
    df_high = pd.DataFrame(rows_high)
    res_high = engine.competition_check(df_high, "python")
    assert res_high["unique_creators_count"] == 16
    assert res_high["competition_label"] == "High"


def test_competition_check_hindi(sample_df):
    """Verify competition check matches Hindi captions and hashtags case-insensitively."""
    # Search for Hindi term 'पनीर' (Paneer)
    res = engine.competition_check(sample_df, "पनीर")
    assert res["matching_videos_count"] >= 1
    assert res["unique_creators_count"] >= 1
    assert len(res["top_videos"]) >= 1
    assert "पनीर" in res["top_videos"].iloc[0]["caption"]


def test_duplicate_detection_hindi(sample_df):
    """Verify duplicate detection correctly identifies similar Hindi ideas with score >= 0.6."""
    # Query very similar to: "वजन घटाने के 5 आसान घरेलू उपाय रोज सुबह फॉलो करें"
    query = "वजन घटाने के 5 आसान घरेलू उपाय रोज सुबह #fitness #fatloss"
    matches = engine.duplicate_check(sample_df, query)

    assert not matches.empty
    assert len(matches) >= 1

    top_match = matches.iloc[0]
    assert top_match["creator"] == "fit_rahul"
    assert top_match["score"] >= 0.6
    assert "वजन घटाने" in top_match["caption"]


def test_duplicate_detection_no_match(sample_df):
    """Verify completely unique caption returns no matches."""
    unique_query = "Quantum computing algorithms for astrophysics and aerospace propulsion"
    matches = engine.duplicate_check(sample_df, unique_query)
    assert matches.empty


def test_save_and_load_owner_checks(tmp_path):
    """Verify manual owner check logging and history retrieval."""
    test_file = str(tmp_path / "test_owner_checks.csv")

    # Initial load on non-existent file
    empty_history = engine.load_owner_checks(test_file)
    assert empty_history.empty
    assert list(empty_history.columns) == ["timestamp", "username", "profile_url", "status", "note"]

    # Save check with @ prefix
    rec1 = engine.save_owner_check("@fit_rahul", "Found", "Verified fitness influencer", filepath=test_file)
    assert rec1["username"] == "fit_rahul"
    assert rec1["profile_url"] == "https://www.tiktok.com/@fit_rahul"
    assert rec1["status"] == "Found"

    # Save second check without @ prefix
    rec2 = engine.save_owner_check("chef_amit", "Not found", "Handle seems inactive", filepath=test_file)
    assert rec2["username"] == "chef_amit"

    # Load history
    history = engine.load_owner_checks(test_file)
    assert len(history) == 2
    assert history.iloc[0]["username"] == "fit_rahul"
    assert history.iloc[1]["username"] == "chef_amit"
    assert history.iloc[0]["status"] == "Found"
    assert history.iloc[1]["status"] == "Not found"

    # Verify empty username raises ValueError
    with pytest.raises(ValueError):
        engine.save_owner_check("   ", "Found", filepath=test_file)
