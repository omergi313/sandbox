"""Streamlit dashboard for Strong app workout analysis."""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

import anthropic
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from strong_analyzer.parser import (
    build_summary,
    load_csv,
    progression_data,
    recent_workouts_detail,
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Strong Workout Dashboard",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] { font-size: 2rem; }
    .block-container { padding-top: 1.5rem; }
    h1 { margin-bottom: 0.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def rows_to_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ("Weight", "Reps", "Distance", "Seconds", "Set Order"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Volume"] = df.get("Weight", 0).fillna(0) * df.get("Reps", 0).fillna(0)
    return df


def estimated_1rm(weight, reps):
    if not weight or not reps or reps <= 0:
        return None
    return round(float(weight) * (1 + float(reps) / 30), 1)


def color_sequence():
    return px.colors.qualitative.Plotly


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("💪 Strong Analyzer")
    st.markdown("---")

    uploaded = st.file_uploader(
        "Upload Strong CSV export",
        type=["csv"],
        help="In Strong: Settings → Export Data → CSV",
    )

    st.markdown("---")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        help="Required for AI analysis tab",
    )

    st.markdown("---")
    st.caption("**How to export from Strong**")
    st.caption("1. Open Strong app")
    st.caption("2. Settings → Export Data")
    st.caption("3. Choose CSV and save")
    st.caption("4. Upload the file above")

# ── Main ──────────────────────────────────────────────────────────────────────

if not uploaded:
    st.title("💪 Strong Workout Dashboard")
    st.markdown(
        """
        ### Get started
        Upload your Strong app CSV export using the sidebar to see:
        - 📊 Strength progression charts for every exercise
        - 🔥 Volume and frequency heatmaps
        - 🏆 Personal records and estimated 1RMs
        - 🤖 AI-powered coaching insights via Claude
        """
    )
    st.info("**Strong app** → Settings → Export Data → CSV", icon="📱")
    st.stop()

# ── Load data ─────────────────────────────────────────────────────────────────

@st.cache_data
def parse_upload(file_bytes: bytes) -> tuple[list[dict], pd.DataFrame]:
    import io, csv, re
    text = file_bytes.decode("utf-8-sig")
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for row in reader:
        cleaned = {}
        for k, v in row.items():
            k = k.strip(); v = v.strip() if v else ""
            if k in ("Weight", "Reps", "Distance", "Seconds", "Set Order", "RPE"):
                try:
                    f = float(v); cleaned[k] = int(f) if f == int(f) else f
                except (ValueError, TypeError):
                    cleaned[k] = None
            elif k == "Date":
                dt = None
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
                    try:
                        dt = datetime.strptime(v, fmt); break
                    except ValueError:
                        pass
                cleaned[k] = dt or v
            else:
                cleaned[k] = v
        rows.append(cleaned)
    df = rows_to_df(rows)
    return rows, df


rows, df = parse_upload(uploaded.read())
summary = build_summary(rows)

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_overview, tab_progress, tab_volume, tab_frequency, tab_prs, tab_ai = st.tabs(
    ["📋 Overview", "📈 Progression", "🔥 Volume", "📅 Frequency", "🏆 PRs & 1RMs", "🤖 AI Coach"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

with tab_overview:
    st.header("Training Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Workouts", summary["total_workouts"])
    c2.metric("Unique Exercises", summary["total_exercises"])
    c3.metric("Avg Sessions / Week", summary["avg_sessions_per_week"])
    c4.metric("Date Range", summary["date_range"].split(" to ")[0][:7] + " → " + summary["date_range"].split(" to ")[-1][:7] if " to " in summary["date_range"] else summary["date_range"])

    st.markdown("---")

    # Top exercises by volume
    st.subheader("Top 10 Exercises by Total Volume (kg × reps)")
    ex_df = pd.DataFrame(summary["exercises"])
    ex_df["Total Volume"] = ex_df["total_reps"] * ex_df["max_weight"]
    top10 = ex_df.nlargest(10, "Total Volume")

    fig = px.bar(
        top10,
        x="Total Volume",
        y="exercise",
        orientation="h",
        color="Total Volume",
        color_continuous_scale="Blues",
        labels={"exercise": ""},
        text="Total Volume",
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(
        height=400,
        coloraxis_showscale=False,
        yaxis={"categoryorder": "total ascending"},
        margin=dict(l=0, r=20, t=10, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Summary table
    st.subheader("All Exercises")
    display_df = ex_df[["exercise", "total_sets", "total_reps", "max_weight", "sessions_count"]].copy()
    display_df.columns = ["Exercise", "Total Sets", "Total Reps", "Max Weight (kg)", "Sessions"]
    display_df = display_df.sort_values("Total Sets", ascending=False).reset_index(drop=True)
    st.dataframe(display_df, use_container_width=True, height=400)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — STRENGTH PROGRESSION
# ══════════════════════════════════════════════════════════════════════════════

with tab_progress:
    st.header("Strength Progression")

    all_exercises = sorted(df["Exercise Name"].dropna().unique())
    default_exercises = (
        pd.DataFrame(summary["exercises"])
        .nlargest(5, "total_sets")["exercise"]
        .tolist()
    )

    selected = st.multiselect(
        "Select exercises to chart",
        options=all_exercises,
        default=[e for e in default_exercises if e in all_exercises],
    )

    metric = st.radio(
        "Y-axis metric",
        ["Max Weight (kg)", "Estimated 1RM (kg)", "Total Volume (kg×reps)"],
        horizontal=True,
    )

    if not selected:
        st.info("Select one or more exercises above.")
    else:
        fig = go.Figure()

        for i, exercise in enumerate(selected):
            ex_df = df[df["Exercise Name"] == exercise].copy()
            ex_df = ex_df.dropna(subset=["Date"])
            ex_df["date_only"] = ex_df["Date"].dt.date

            if metric == "Max Weight (kg)":
                grouped = ex_df.groupby("date_only")["Weight"].max().reset_index()
                y_col = "Weight"
            elif metric == "Estimated 1RM (kg)":
                ex_df["e1rm"] = ex_df.apply(
                    lambda r: estimated_1rm(r["Weight"], r["Reps"]), axis=1
                )
                grouped = ex_df.groupby("date_only")["e1rm"].max().reset_index()
                y_col = "e1rm"
            else:
                grouped = ex_df.groupby("date_only")["Volume"].sum().reset_index()
                y_col = "Volume"

            grouped = grouped.dropna(subset=[y_col])

            fig.add_trace(
                go.Scatter(
                    x=grouped["date_only"],
                    y=grouped[y_col],
                    mode="lines+markers",
                    name=exercise,
                    line=dict(width=2),
                    marker=dict(size=6),
                )
            )

        fig.update_layout(
            height=480,
            xaxis_title="Date",
            yaxis_title=metric,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=0, r=0, t=30, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — VOLUME
# ══════════════════════════════════════════════════════════════════════════════

with tab_volume:
    st.header("Training Volume")

    df_v = df.dropna(subset=["Date"]).copy()
    df_v["Week"] = df_v["Date"].dt.to_period("W").apply(lambda p: p.start_time)
    df_v["Month"] = df_v["Date"].dt.to_period("M").apply(lambda p: p.start_time)

    granularity = st.radio("Granularity", ["Weekly", "Monthly"], horizontal=True)
    group_col = "Week" if granularity == "Weekly" else "Month"

    # Total volume over time
    vol_time = df_v.groupby(group_col)["Volume"].sum().reset_index()
    fig1 = px.bar(
        vol_time,
        x=group_col,
        y="Volume",
        title=f"{granularity} Total Volume (kg × reps)",
        color="Volume",
        color_continuous_scale="Oranges",
    )
    fig1.update_layout(coloraxis_showscale=False, height=320, margin=dict(t=40, b=0))
    st.plotly_chart(fig1, use_container_width=True)

    # Volume by exercise (top 8)
    st.subheader("Volume Distribution by Exercise")
    top8 = (
        df_v.groupby("Exercise Name")["Volume"]
        .sum()
        .nlargest(8)
        .index.tolist()
    )
    df_top8 = df_v[df_v["Exercise Name"].isin(top8)]
    vol_ex = df_top8.groupby([group_col, "Exercise Name"])["Volume"].sum().reset_index()

    fig2 = px.area(
        vol_ex,
        x=group_col,
        y="Volume",
        color="Exercise Name",
        title=f"{granularity} Volume — Top 8 Exercises",
        color_discrete_sequence=color_sequence(),
    )
    fig2.update_layout(height=380, margin=dict(t=40, b=0), hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

    # Sets per session
    st.subheader("Sets Per Workout Session")
    df_v["date_only"] = df_v["Date"].dt.date
    sets_per_session = df_v.groupby("date_only").size().reset_index(name="Sets")
    fig3 = px.scatter(
        sets_per_session,
        x="date_only",
        y="Sets",
        trendline="lowess",
        title="Total Sets per Session",
    )
    fig3.update_layout(height=300, margin=dict(t=40, b=0))
    st.plotly_chart(fig3, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — FREQUENCY / CALENDAR HEATMAP
# ══════════════════════════════════════════════════════════════════════════════

with tab_frequency:
    st.header("Workout Frequency")

    df_f = df.dropna(subset=["Date"]).copy()
    df_f["date_only"] = df_f["Date"].dt.date

    workout_days = df_f.groupby("date_only").size().reset_index(name="sets")
    workout_days["date"] = pd.to_datetime(workout_days["date_only"])
    workout_days["dow"] = workout_days["date"].dt.dayofweek   # 0=Mon
    workout_days["week"] = workout_days["date"].dt.isocalendar().week.astype(int)
    workout_days["year"] = workout_days["date"].dt.year
    workout_days["year_week"] = (
        workout_days["year"].astype(str) + "-W" + workout_days["week"].astype(str).str.zfill(2)
    )

    # Last 52 weeks heatmap
    st.subheader("Last 52 Weeks — Training Calendar")
    cutoff = pd.Timestamp.today() - pd.Timedelta(weeks=52)
    recent_wd = workout_days[workout_days["date"] >= cutoff].copy()

    # Build full grid
    all_days = pd.date_range(cutoff.floor("D"), pd.Timestamp.today().floor("D"))
    grid = pd.DataFrame({"date": all_days})
    grid["dow"] = grid["date"].dt.dayofweek
    grid["week_num"] = (grid["date"] - cutoff.floor("D")).dt.days // 7
    grid = grid.merge(
        recent_wd[["date", "sets"]].rename(columns={"date": "date"}),
        on="date",
        how="left",
    )
    grid["sets"] = grid["sets"].fillna(0)

    fig_cal = go.Figure(
        go.Heatmap(
            x=grid["week_num"],
            y=grid["dow"],
            z=grid["sets"],
            colorscale=[[0, "#ebedf0"], [0.01, "#9be9a8"], [0.3, "#40c463"], [0.7, "#30a14e"], [1, "#216e39"]],
            xgap=2,
            ygap=2,
            showscale=False,
            hovertemplate="<b>%{customdata}</b><br>Sets: %{z}<extra></extra>",
            customdata=grid["date"].dt.strftime("%a %b %-d %Y"),
        )
    )
    fig_cal.update_layout(
        height=200,
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(7)),
            ticktext=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            autorange="reversed",
        ),
        xaxis=dict(showticklabels=False),
        margin=dict(l=40, r=0, t=10, b=10),
    )
    st.plotly_chart(fig_cal, use_container_width=True)

    # Day of week breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Favourite Training Days")
        dow_counts = workout_days.groupby("dow").size().reset_index(name="workouts")
        dow_counts["day"] = dow_counts["dow"].map(
            {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        )
        fig_dow = px.bar(
            dow_counts,
            x="day",
            y="workouts",
            color="workouts",
            color_continuous_scale="Greens",
        )
        fig_dow.update_layout(coloraxis_showscale=False, height=280, margin=dict(t=0))
        st.plotly_chart(fig_dow, use_container_width=True)

    with col2:
        st.subheader("Monthly Workout Count")
        df_f["month"] = df_f["Date"].dt.to_period("M").apply(lambda p: p.start_time)
        monthly = df_f.groupby("month")["date_only"].nunique().reset_index(name="workouts")
        fig_month = px.line(
            monthly, x="month", y="workouts", markers=True, color_discrete_sequence=["#40c463"]
        )
        fig_month.update_layout(height=280, margin=dict(t=0))
        st.plotly_chart(fig_month, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — PRs & ESTIMATED 1RMs
# ══════════════════════════════════════════════════════════════════════════════

with tab_prs:
    st.header("Personal Records & Estimated 1RMs")

    df_pr = df.dropna(subset=["Weight", "Reps"]).copy()
    df_pr = df_pr[df_pr["Weight"] > 0]
    df_pr["e1rm"] = df_pr.apply(lambda r: estimated_1rm(r["Weight"], r["Reps"]), axis=1)

    # Best e1rm per exercise
    pr_table = (
        df_pr.groupby("Exercise Name")
        .agg(
            max_weight=("Weight", "max"),
            best_e1rm=("e1rm", "max"),
            total_sets=("Set Order", "count"),
        )
        .reset_index()
        .sort_values("best_e1rm", ascending=False)
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Estimated 1RM — Top 15 Exercises")
        top15 = pr_table.head(15)
        fig_pr = px.bar(
            top15,
            x="best_e1rm",
            y="Exercise Name",
            orientation="h",
            color="best_e1rm",
            color_continuous_scale="Reds",
            text="best_e1rm",
            labels={"Exercise Name": "", "best_e1rm": "Est. 1RM (kg)"},
        )
        fig_pr.update_traces(texttemplate="%{text:.1f} kg", textposition="outside")
        fig_pr.update_layout(
            coloraxis_showscale=False,
            height=460,
            yaxis={"categoryorder": "total ascending"},
            margin=dict(l=0, r=40, t=10, b=0),
        )
        st.plotly_chart(fig_pr, use_container_width=True)

    with col2:
        st.subheader("PR Table")
        pr_display = pr_table[["Exercise Name", "max_weight", "best_e1rm"]].copy()
        pr_display.columns = ["Exercise", "Max Weight", "Est. 1RM"]
        pr_display["Max Weight"] = pr_display["Max Weight"].map("{:.1f} kg".format)
        pr_display["Est. 1RM"] = pr_display["Est. 1RM"].map("{:.1f} kg".format)
        st.dataframe(pr_display, use_container_width=True, height=460, hide_index=True)

    # e1RM progression for selected exercise
    st.markdown("---")
    st.subheader("1RM Progression Over Time")
    selected_pr_ex = st.selectbox(
        "Choose exercise",
        options=pr_table["Exercise Name"].tolist(),
        key="pr_exercise",
    )
    ex_prog = df_pr[df_pr["Exercise Name"] == selected_pr_ex].copy()
    ex_prog["date_only"] = ex_prog["Date"].dt.date
    prog_grouped = ex_prog.groupby("date_only")["e1rm"].max().reset_index()

    fig_prog = go.Figure()
    fig_prog.add_trace(
        go.Scatter(
            x=prog_grouped["date_only"],
            y=prog_grouped["e1rm"],
            mode="lines+markers",
            fill="tozeroy",
            fillcolor="rgba(255,80,80,0.15)",
            line=dict(color="tomato", width=2),
            marker=dict(size=7, color="tomato"),
            name="Est. 1RM",
        )
    )
    fig_prog.update_layout(
        height=320,
        xaxis_title="Date",
        yaxis_title="Estimated 1RM (kg)",
        margin=dict(l=0, r=0, t=10, b=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig_prog, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — AI COACH
# ══════════════════════════════════════════════════════════════════════════════

with tab_ai:
    st.header("AI Coach — Powered by Claude")

    if not api_key:
        st.warning(
            "Enter your Anthropic API key in the sidebar to enable AI analysis.",
            icon="🔑",
        )
        st.stop()

    analysis_type = st.radio(
        "Analysis type",
        ["Full Analysis", "Ask a Question", "Progression Analysis"],
        horizontal=True,
    )

    user_question = None
    track_exercises = []

    if analysis_type == "Ask a Question":
        user_question = st.text_input(
            "Your question",
            placeholder="e.g. Am I overtraining chest? What should I improve?",
        )
    elif analysis_type == "Progression Analysis":
        track_exercises = st.multiselect(
            "Select exercises to analyse progression",
            options=sorted(df["Exercise Name"].dropna().unique()),
            default=[e["exercise"] for e in summary["exercises"][:3]],
        )

    if st.button("🤖 Analyse with Claude", type="primary"):
        if analysis_type == "Ask a Question" and not user_question:
            st.error("Please enter a question.")
        else:
            with st.spinner("Claude is analysing your workouts..."):
                try:
                    client = anthropic.Anthropic(api_key=api_key)

                    # Build progressions
                    progressions = {}
                    exercises_to_track = track_exercises or [
                        e["exercise"] for e in sorted(
                            summary["exercises"], key=lambda x: x["total_sets"], reverse=True
                        )[:5]
                    ]
                    for ex in exercises_to_track:
                        prog = progression_data(rows, ex)
                        if prog:
                            progressions[ex] = prog

                    recent = recent_workouts_detail(rows, n=10)

                    data_block = json.dumps(
                        {
                            "overall_summary": summary,
                            "recent_workouts": recent,
                            "exercise_progressions": progressions,
                        },
                        indent=2,
                        default=str,
                    )

                    prompt = f"Here is my Strong app workout data:\n\n```json\n{data_block}\n```\n\n"
                    if analysis_type == "Ask a Question":
                        prompt += f"My specific question: {user_question}"
                    elif analysis_type == "Progression Analysis":
                        prompt += (
                            "Analyse my progression for the exercises in 'exercise_progressions'. "
                            "For each: identify trend (improving/plateau/declining), estimate when I might hit the next milestone, "
                            "and give specific advice."
                        )
                    else:
                        prompt += (
                            "Provide a comprehensive training analysis. Cover: "
                            "1) training consistency and volume trends, "
                            "2) strength progress per exercise, "
                            "3) potential muscle imbalances, "
                            "4) recovery patterns, "
                            "5) top 5 actionable recommendations with specific numbers."
                        )

                    message = client.messages.create(
                        model="claude-opus-4-6",
                        max_tokens=4096,
                        system=(
                            "You are an expert strength & conditioning coach. Analyse the workout data "
                            "and provide specific, data-driven insights. Reference actual numbers from "
                            "the data. Be concise, practical, and encouraging. Use markdown formatting."
                        ),
                        messages=[{"role": "user", "content": prompt}],
                    )

                    result = message.content[0].text
                    st.session_state["last_analysis"] = result

                except anthropic.AuthenticationError:
                    st.error("Invalid API key. Check your Anthropic API key.")
                except Exception as e:
                    st.error(f"Error calling Claude: {e}")

    if "last_analysis" in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state["last_analysis"])
