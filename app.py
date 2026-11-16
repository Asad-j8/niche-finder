"""
TikTok All-Niche Finder
A Streamlit web application for analyzing TikTok niches, checking competition,
detecting duplicate content ideas, and logging creator owner checks.
Fully offline analysis running exclusively on user-provided CSV data.
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import streamlit as st

import niche_engine as engine

# Page configuration
st.set_page_config(
    page_title="TikTok All-Niche Finder",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom header styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #6c757d;
        margin-bottom: 1.5rem;
    }
    .badge-low {
        background-color: #d4edda;
        color: #155724;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-medium {
        background-color: #fff3cd;
        color: #856404;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-high {
        background-color: #f8d7da;
        color: #721c24;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-header">🎯 TikTok All-Niche Finder</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Free, open-source TikTok niche intelligence & opportunity analysis. Runs 100% offline on your uploaded CSV data.</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Sidebar: CSV Upload & Dataset Controls
# ---------------------------------------------------------
st.sidebar.header("📁 Dataset")
uploaded_file = st.sidebar.file_uploader(
    "Upload TikTok CSV",
    type=["csv"],
    help="Required columns: niche, hashtag, caption, creator, views, likes, video_url",
)

sample_csv_path = os.path.join(os.path.dirname(__file__), "data", "sample.csv")
use_sample = False
if uploaded_file is None:
    if os.path.exists(sample_csv_path):
        use_sample = True
        st.sidebar.info("Using bundled `data/sample.csv` (35 videos across 5 niches). Upload your own CSV above anytime.")
    else:
        st.sidebar.warning("Please upload a CSV file with the required columns.")

# Load and validate dataset
df: Optional[pd.DataFrame] = None
data_error: Optional[str] = None

try:
    if uploaded_file is not None:
        df = engine.load_videos(uploaded_file)
    elif use_sample and os.path.exists(sample_csv_path):
        df = engine.load_videos(sample_csv_path)
except ValueError as e:
    data_error = str(e)
except Exception as e:
    data_error = f"Error loading CSV: {e}"

if data_error:
    st.error(f"❌ {data_error}")
    st.markdown(
        """
        **Required Columns in CSV:**
        - `niche`: Category / Niche name (e.g. fitness, cooking, finance)
        - `hashtag`: Associated hashtags (e.g. `#fitness #gym`)
        - `caption`: Video caption (English or Hindi / Devanagari)
        - `creator`: Creator username
        - `views`: Number of views
        - `likes`: Number of likes
        - `video_url`: TikTok video URL
        """
    )
    st.stop()

if df is None or df.empty:
    st.info("👋 Upload a CSV file in the sidebar to get started!")
    st.stop()

# Sidebar Dataset Summary
st.sidebar.subheader("📊 Dataset Overview")
st.sidebar.metric("Total Videos", f"{len(df):,}")
st.sidebar.metric("Unique Niches", f"{df['niche'].nunique():,}")
st.sidebar.metric("Unique Creators", f"{df['creator'].nunique():,}")
st.sidebar.metric("Total Views", f"{df['views'].sum():,}")

# ---------------------------------------------------------
# Tabs: Niche Analysis, Competition Check, Duplicate Check, Owner Check
# ---------------------------------------------------------
tab_niche, tab_comp, tab_dup, tab_owner = st.tabs(
    [
        "📊 Niche Analysis",
        "🔍 Competition Check",
        "⚡ Duplicate Check",
        "👤 Owner Check",
    ]
)

# =========================================================
# FEATURE 1: Niche Analysis
# =========================================================
with tab_niche:
    st.subheader("Niche Performance & Opportunity Scoring")
    st.markdown(
        """
        Opportunity score is calculated based on **Demand** (average views relative to highest niche)
        and **Competition** (creator density):
        $$\\text{Opportunity Score} = \\text{Demand} \\times (1 - \\text{Competition}) \\times 100$$
        """
    )

    all_niches = sorted(df["niche"].unique().tolist())
    selected_niches = st.multiselect(
        "Filter Niches:",
        options=all_niches,
        default=all_niches,
        help="Select one or more niches to include in the analysis",
    )

    if not selected_niches:
        st.warning("Please select at least one niche to view analysis.")
    else:
        score_df = engine.score_niches(df, selected_niches=selected_niches)

        if score_df.empty:
            st.info("No data available for selected niches.")
        else:
            # Top metrics
            best_opportunity = score_df.iloc[0]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Top Opportunity Niche",
                    best_opportunity["niche"].title(),
                    f"Score: {best_opportunity['opportunity_score']:.1f}",
                )
            with col2:
                highest_demand = score_df.sort_values(by="avg_views", ascending=False).iloc[0]
                st.metric(
                    "Highest Demand Niche",
                    highest_demand["niche"].title(),
                    f"{int(highest_demand['avg_views']):,} avg views",
                )
            with col3:
                lowest_comp = score_df.sort_values(by="competition", ascending=True).iloc[0]
                st.metric(
                    "Lowest Competition Niche",
                    lowest_comp["niche"].title(),
                    f"{lowest_comp['unique_creators']} creators",
                )

            # Sortable Table
            st.markdown("#### Niche Opportunity Ranking")
            display_df = score_df.copy()
            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "niche": st.column_config.TextColumn("Niche"),
                    "video_count": st.column_config.NumberColumn("Videos", format="%d"),
                    "unique_creators": st.column_config.NumberColumn("Creators", format="%d"),
                    "avg_views": st.column_config.NumberColumn("Avg Views", format="%,d"),
                    "median_views": st.column_config.NumberColumn("Median Views", format="%,d"),
                    "top_views": st.column_config.NumberColumn("Top Views", format="%,d"),
                    "competition": st.column_config.ProgressColumn(
                        "Competition (0-1)", min_value=0.0, max_value=1.0, format="%.2f"
                    ),
                    "demand": st.column_config.ProgressColumn(
                        "Demand (0-1)", min_value=0.0, max_value=1.0, format="%.2f"
                    ),
                    "opportunity_score": st.column_config.NumberColumn(
                        "Opportunity Score (0-100)", format="%.1f"
                    ),
                },
                hide_index=True,
            )

            # Bar Chart
            st.markdown("#### Opportunity Score by Niche")
            chart_data = score_df.set_index("niche")[["opportunity_score"]]
            st.bar_chart(chart_data)

# =========================================================
# FEATURE 2: Competition Check
# =========================================================
with tab_comp:
    st.subheader("Topic / Keyword Competition Check")
    st.markdown(
        "Search across caption and hashtag columns in Hindi (Devanagari) or English to measure creator competition."
    )

    search_kw = st.text_input(
        "Enter keyword or topic (e.g. fitness, पनीर, budget, travel, शादी):",
        placeholder="Type keyword here...",
    )

    if search_kw.strip():
        comp_result = engine.competition_check(df, search_kw.strip())

        m_count = comp_result["matching_videos_count"]
        c_count = comp_result["unique_creators_count"]
        label = comp_result["competition_label"]
        top_matches = comp_result["top_videos"]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Matching Videos", f"{m_count}")
        with col2:
            st.metric("Unique Creators", f"{c_count}")
        with col3:
            badge_class = f"badge-{label.lower()}"
            st.markdown(
                f"""
                <div style="padding-top: 10px;">
                    <div style="font-size: 0.85rem; color: #6c757d;">Competition Level</div>
                    <span class="{badge_class}" style="font-size: 1.15rem;">{label}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.caption(
            f"Thresholds: Low (< {engine.COMPETITION_LOW_MAX} creators), "
            f"Medium ({engine.COMPETITION_LOW_MAX} to {engine.COMPETITION_MED_MAX} creators), "
            f"High (> {engine.COMPETITION_MED_MAX} creators)"
        )

        if m_count > 0:
            st.markdown("#### Top 10 Matching Videos by Views")
            st.dataframe(
                top_matches[["creator", "niche", "views", "likes", "caption", "video_url"]],
                use_container_width=True,
                column_config={
                    "video_url": st.column_config.LinkColumn("TikTok Video Link", display_text="Open Video 🔗"),
                    "views": st.column_config.NumberColumn("Views", format="%,d"),
                    "likes": st.column_config.NumberColumn("Likes", format="%,d"),
                },
                hide_index=True,
            )
        else:
            st.info(f"No videos found matching '{search_kw}'. Try another keyword.")
    else:
        st.info("Enter a keyword above to inspect creator competition and top performing videos.")

# =========================================================
# FEATURE 3: Duplicate Check
# =========================================================
with tab_dup:
    st.subheader("Duplicate Idea & Caption Check")
    st.markdown(
        """
        Paste a video caption or idea. The engine computes:
        $$\\text{Final Score} = 0.7 \\times \\text{Text Similarity} + 0.3 \\times \\text{Hashtag Overlap}$$
        Displays matching content with similarity score $\\ge 0.60$.
        """
    )
    st.info("ℹ️ **Note**: This check only analyzes the uploaded CSV dataset, not all of TikTok.")

    user_caption = st.text_area(
        "Paste caption or video idea to check:",
        height=100,
        placeholder="e.g. वजन घटाने के 5 आसान घरेलू उपाय #fitness #weightloss",
    )

    if st.button("Check for Duplicates", type="primary"):
        if not user_caption.strip():
            st.warning("Please enter a caption or idea to check.")
        else:
            matches_df = engine.duplicate_check(df, user_caption.strip())

            if matches_df.empty:
                st.success("Is data mein koi milta-julta content nahi mila.")
            else:
                st.warning(f"Found {len(matches_df)} similar video idea(s) in this dataset!")
                st.dataframe(
                    matches_df,
                    use_container_width=True,
                    column_config={
                        "score": st.column_config.NumberColumn("Final Match Score", format="%.3f"),
                        "text_similarity": st.column_config.NumberColumn("Text Similarity", format="%.3f"),
                        "hashtag_overlap": st.column_config.NumberColumn("Hashtag Overlap", format="%.3f"),
                        "video_url": st.column_config.LinkColumn("Video Link", display_text="Open Video 🔗"),
                        "views": st.column_config.NumberColumn("Views", format="%,d"),
                    },
                    hide_index=True,
                )

# =========================================================
# FEATURE 4: Creator Owner Check
# =========================================================
with tab_owner:
    st.subheader("Creator Owner Check")
    st.markdown(
        """
        Look up a creator's profile link and manually log verification notes.
        *Note: This tool never sends automated requests or scrapes TikTok.*
        """
    )

    owner_input = st.text_input("Enter TikTok username (with or without @):", placeholder="e.g. fit_rahul or @fit_rahul")

    if owner_input.strip():
        clean_user = owner_input.strip().lstrip("@")
        profile_url = f"https://www.tiktok.com/@{clean_user}"

        st.markdown(f"🔗 **TikTok Profile Link:** [{profile_url}]({profile_url})")

        with st.form("owner_check_form"):
            st.markdown("##### Record Manual Verification")
            status = st.radio("Verification Status:", ["Found", "Not found", "Unsure"], horizontal=True)
            note = st.text_input("Notes / Remarks:", placeholder="e.g. Active creator in fitness niche with 50k followers")
            submitted = st.form_submit_button("Save Result", type="primary")

            if submitted:
                engine.save_owner_check(clean_user, status, note)
                st.success(f"Result for @{clean_user} saved successfully!")

    # Display saved history
    st.markdown("---")
    st.markdown("#### 📜 Manual Verification History")
    history_df = engine.load_owner_checks()
    if history_df.empty:
        st.caption("No manual owner checks logged yet. Enter a username above to record your first check.")
    else:
        st.dataframe(
            history_df,
            use_container_width=True,
            column_config={
                "profile_url": st.column_config.LinkColumn("Profile URL", display_text="Open Profile 🔗"),
                "timestamp": st.column_config.TextColumn("Date & Time"),
            },
            hide_index=True,
        )
