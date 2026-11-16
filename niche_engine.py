"""
Core logic and analysis engine for TikTok All-Niche Finder.
Pure functions only, with no Streamlit imports, to ensure full testability.
"""

from __future__ import annotations

import difflib
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import pandas as pd

# Required CSV columns
REQUIRED_COLUMNS: List[str] = [
    "niche",
    "hashtag",
    "caption",
    "creator",
    "views",
    "likes",
    "video_url",
]

# Competition thresholds based on unique creator count
COMPETITION_LOW_MAX: int = 5  # under 5 creators -> Low
COMPETITION_MED_MAX: int = 15  # 5 to 15 creators -> Medium, over 15 -> High

# Duplicate check similarity weights and match threshold
SIMILARITY_TEXT_WEIGHT: float = 0.7
SIMILARITY_HASHTAG_WEIGHT: float = 0.3
DUPLICATE_THRESHOLD: float = 0.6

# Default file path for owner checks history
DEFAULT_OWNER_CHECKS_FILE: str = "owner_checks.csv"


def extract_hashtags(text: str) -> Set[str]:
    """
    Extract all hashtags from text in lowercase.
    Supports English alphanumeric and Devanagari (Hindi) characters.
    """
    if not isinstance(text, str):
        return set()
    # Matches # followed by alphanumeric, underscore, or Devanagari range \u0900-\u097F
    matches = re.findall(r"#([a-zA-Z0-9_\u0900-\u097f]+)", text)
    return {m.lower() for m in matches}


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison:
    - Lowercase
    - Remove hashtags and punctuation
    - Keep only a-z, 0-9, and Devanagari characters (\u0900-\u097F)
    - Collapse multiple spaces
    """
    if not text or not isinstance(text, str):
        return ""

    lowered = text.lower()
    # Remove hashtag tokens (e.g. #fitness, #वजन)
    without_hashtags = re.sub(r"#\S+", " ", lowered)
    # Retain only a-z, 0-9, Devanagari \u0900-\u097F, and spaces
    cleaned = re.sub(r"[^a-z0-9\u0900-\u097f\s]", " ", without_hashtags)
    # Collapse multiple whitespace characters into single space
    normalized = re.sub(r"\s+", " ", cleaned).strip()
    return normalized


def load_videos(file_path_or_buffer: Any) -> pd.DataFrame:
    """
    Load and validate TikTok video records from a CSV file path or file-like buffer.
    Reads with encoding='utf-8-sig' to support Hindi (Devanagari) and English.
    Validates required columns and cleans numeric fields (views, likes).
    Raises ValueError listing all missing columns if any required column is absent.
    """
    try:
        df = pd.read_csv(file_path_or_buffer, encoding="utf-8-sig")
    except Exception as e:
        raise ValueError(f"Could not read CSV file: {e}") from e

    # Check for missing required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    # Clean text columns
    text_columns = ["niche", "hashtag", "caption", "creator", "video_url"]
    for col in text_columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Convert numeric columns; treat invalid / NaN values as 0
    df["views"] = (
        pd.to_numeric(df["views"], errors="coerce")
        .fillna(0)
        .clip(lower=0)
        .astype(int)
    )
    df["likes"] = (
        pd.to_numeric(df["likes"], errors="coerce")
        .fillna(0)
        .clip(lower=0)
        .astype(int)
    )

    return df


def score_niches(
    df: pd.DataFrame, selected_niches: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Analyze and score niches from the dataset.
    For each niche computes:
      - video_count
      - unique_creators
      - avg_views
      - median_views
      - top_views
      - competition = unique_creators / max(unique_creators) (0 to 1)
      - demand = avg_views / max(avg_views) (0 to 1)
      - opportunity_score = round(demand * (1 - competition) * 100, 1)

    Returns a DataFrame sorted descending by opportunity_score.
    """
    columns = [
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

    if df.empty:
        return pd.DataFrame(columns=columns)

    working_df = df.copy()
    if selected_niches:
        working_df = working_df[working_df["niche"].isin(selected_niches)]

    if working_df.empty:
        return pd.DataFrame(columns=columns)

    records = []
    for niche_name, group in working_df.groupby("niche"):
        v_count = int(len(group))
        u_creators = int(group["creator"].nunique())
        avg_views = float(group["views"].mean()) if v_count > 0 else 0.0
        median_views = float(group["views"].median()) if v_count > 0 else 0.0
        top_views = int(group["views"].max()) if v_count > 0 else 0

        records.append(
            {
                "niche": str(niche_name),
                "video_count": v_count,
                "unique_creators": u_creators,
                "avg_views": round(avg_views, 1),
                "median_views": round(median_views, 1),
                "top_views": top_views,
            }
        )

    if not records:
        return pd.DataFrame(columns=columns)

    score_df = pd.DataFrame(records)

    max_creators = score_df["unique_creators"].max()
    max_avg_views = score_df["avg_views"].max()

    score_df["competition"] = (
        (score_df["unique_creators"] / max_creators).round(3)
        if max_creators > 0
        else 0.0
    )
    score_df["demand"] = (
        (score_df["avg_views"] / max_avg_views).round(3)
        if max_avg_views > 0
        else 0.0
    )
    score_df["opportunity_score"] = (
        score_df["demand"] * (1.0 - score_df["competition"]) * 100.0
    ).round(1)

    # Sort descending by opportunity_score, secondary sort by avg_views
    score_df = score_df.sort_values(
        by=["opportunity_score", "avg_views"], ascending=[False, False]
    ).reset_index(drop=True)

    return score_df[columns]


def competition_check(df: pd.DataFrame, keyword: str) -> Dict[str, Any]:
    """
    Check competition for a given keyword or topic across caption and hashtag columns.
    Case-insensitive search supporting both Hindi (Devanagari) and English.
    Returns:
      - matching_videos_count
      - unique_creators_count
      - competition_label ("Low", "Medium", or "High")
      - top_videos (DataFrame of top 10 matching videos by views)
    """
    columns = REQUIRED_COLUMNS

    kw = str(keyword).strip().lower() if keyword else ""
    if not kw or df.empty:
        return {
            "matching_videos_count": 0,
            "unique_creators_count": 0,
            "competition_label": "Low",
            "top_videos": pd.DataFrame(columns=columns),
        }

    # Case-insensitive substring match in caption or hashtag
    mask = df["caption"].str.lower().str.contains(
        kw, regex=False, na=False
    ) | df["hashtag"].str.lower().str.contains(kw, regex=False, na=False)

    matches = df[mask].copy()
    match_count = int(len(matches))
    unique_creators = int(matches["creator"].nunique()) if match_count > 0 else 0

    if unique_creators < COMPETITION_LOW_MAX:
        competition_label = "Low"
    elif unique_creators <= COMPETITION_MED_MAX:
        competition_label = "Medium"
    else:
        competition_label = "High"

    top_videos = (
        matches.sort_values(by="views", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    return {
        "matching_videos_count": match_count,
        "unique_creators_count": unique_creators,
        "competition_label": competition_label,
        "top_videos": top_videos,
    }


def duplicate_check(df: pd.DataFrame, query_text: str) -> pd.DataFrame:
    """
    Compare query_text against every video in df:
      - text_similarity: difflib.SequenceMatcher ratio on normalized texts
      - hashtag_overlap: Jaccard similarity of extracted hashtags
      - final_score = 0.7 * text_similarity + 0.3 * hashtag_overlap
    Returns matches with score >= DUPLICATE_THRESHOLD (0.6), sorted by score descending.
    """
    result_columns = [
        "creator",
        "caption",
        "video_url",
        "score",
        "text_similarity",
        "hashtag_overlap",
        "views",
    ]

    if not query_text or df.empty:
        return pd.DataFrame(columns=result_columns)

    query_norm = normalize_text(query_text)
    query_tags = extract_hashtags(query_text)

    if not query_norm and not query_tags:
        return pd.DataFrame(columns=result_columns)

    matches = []
    for _, row in df.iterrows():
        target_caption = str(row["caption"])
        target_norm = normalize_text(target_caption)

        # Compute text similarity
        if query_norm and target_norm:
            text_sim = difflib.SequenceMatcher(
                None, query_norm, target_norm
            ).ratio()
        else:
            text_sim = 0.0

        # Compute hashtag overlap (combine target hashtag column and caption hashtags)
        combined_target_text = f"{row['hashtag']} {target_caption}"
        target_tags = extract_hashtags(combined_target_text)

        tag_union = query_tags | target_tags
        if tag_union:
            tag_overlap = len(query_tags & target_tags) / len(tag_union)
        else:
            tag_overlap = 0.0

        final_score = round(
            (SIMILARITY_TEXT_WEIGHT * text_sim)
            + (SIMILARITY_HASHTAG_WEIGHT * tag_overlap),
            3,
        )

        if final_score >= DUPLICATE_THRESHOLD:
            matches.append(
                {
                    "creator": row["creator"],
                    "caption": row["caption"],
                    "video_url": row["video_url"],
                    "score": final_score,
                    "text_similarity": round(text_sim, 3),
                    "hashtag_overlap": round(tag_overlap, 3),
                    "views": row["views"],
                }
            )

    if not matches:
        return pd.DataFrame(columns=result_columns)

    match_df = pd.DataFrame(matches)
    match_df = match_df.sort_values(
        by=["score", "views"], ascending=[False, False]
    ).reset_index(drop=True)
    return match_df[result_columns]


def save_owner_check(
    username: str,
    status: str,
    note: str = "",
    filepath: str = DEFAULT_OWNER_CHECKS_FILE,
) -> Dict[str, str]:
    """
    Save manual owner check result to local CSV file.
    Does NOT make automated requests to TikTok.
    """
    clean_username = str(username).strip().lstrip("@")
    if not clean_username:
        raise ValueError("Username cannot be empty")

    status_clean = str(status).strip()
    profile_url = f"https://www.tiktok.com/@{clean_username}"
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "timestamp": timestamp_str,
        "username": clean_username,
        "profile_url": profile_url,
        "status": status_clean,
        "note": str(note).strip(),
    }

    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    new_df = pd.DataFrame([record])
    new_df.to_csv(
        filepath,
        mode="a",
        header=not file_exists,
        index=False,
        encoding="utf-8-sig",
    )
    return record


def load_owner_checks(filepath: str = DEFAULT_OWNER_CHECKS_FILE) -> pd.DataFrame:
    """
    Load owner check history from local CSV file.
    Returns empty DataFrame if file does not exist.
    """
    columns = ["timestamp", "username", "profile_url", "status", "note"]
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        try:
            df = pd.read_csv(filepath, encoding="utf-8-sig")
            # Ensure all standard columns exist
            for col in columns:
                if col not in df.columns:
                    df[col] = ""
            return df[columns]
        except Exception:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)
