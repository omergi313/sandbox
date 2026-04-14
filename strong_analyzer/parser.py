"""Parse and summarize Strong app CSV exports."""

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_csv(path: str) -> list[dict]:
    """Load a Strong app CSV export and return rows as dicts."""
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        # Auto-detect delimiter: Strong uses ";" in some locales, "," in others
        sample = f.read(2048)
        f.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            rows.append(_clean_row(row))
    return rows


def _clean_row(row: dict) -> dict:
    """Normalise a single CSV row: strip keys, parse numbers."""
    cleaned = {}
    for key, val in row.items():
        key = key.strip()
        val = val.strip() if val else ""
        if key in ("Weight", "Reps", "Distance", "Seconds", "Set Order", "RPE"):
            cleaned[key] = _to_number(val)
        elif key == "Date":
            cleaned[key] = _parse_date(val)
        else:
            cleaned[key] = val
    return cleaned


def _to_number(val: str):
    """Convert string to int or float, or None."""
    if not val:
        return None
    try:
        f = float(val)
        return int(f) if f == int(f) else f
    except ValueError:
        return None


def _parse_date(val: str):
    """Try common Strong date formats."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return val  # return raw string if nothing matches


def build_summary(rows: list[dict]) -> dict:
    """Build a structured summary of the workout data."""
    if not rows:
        return {"error": "No data found"}

    exercises = defaultdict(lambda: {"sets": 0, "total_reps": 0, "max_weight": 0, "sessions": set()})
    workouts_by_date = defaultdict(list)
    all_exercises = set()

    for row in rows:
        name = row.get("Exercise Name", "Unknown")
        date = row.get("Date")
        weight = row.get("Weight") or 0
        reps = row.get("Reps") or 0

        all_exercises.add(name)
        exercises[name]["sets"] += 1
        exercises[name]["total_reps"] += reps
        exercises[name]["max_weight"] = max(exercises[name]["max_weight"], weight)
        if date:
            date_key = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10]
            exercises[name]["sessions"].add(date_key)
            workouts_by_date[date_key].append(row)

    # Compute date range
    dates = sorted(workouts_by_date.keys())
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "unknown"

    # Per-exercise summary
    exercise_summaries = []
    for name in sorted(all_exercises):
        info = exercises[name]
        exercise_summaries.append({
            "exercise": name,
            "total_sets": info["sets"],
            "total_reps": info["total_reps"],
            "max_weight": info["max_weight"],
            "sessions_count": len(info["sessions"]),
        })

    # Weekly frequency
    weeks = defaultdict(int)
    for date_str in dates:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        week_key = dt.strftime("%Y-W%W")
        weeks[week_key] += 1
    avg_sessions_per_week = round(sum(weeks.values()) / max(len(weeks), 1), 1)

    return {
        "date_range": date_range,
        "total_workouts": len(dates),
        "total_exercises": len(all_exercises),
        "avg_sessions_per_week": avg_sessions_per_week,
        "exercises": exercise_summaries,
    }


def recent_workouts_detail(rows: list[dict], n: int = 10) -> list[dict]:
    """Return the last N workout sessions with full set details."""
    workouts_by_date = defaultdict(list)
    for row in rows:
        date = row.get("Date")
        date_key = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10]
        workouts_by_date[date_key].append(row)

    sorted_dates = sorted(workouts_by_date.keys(), reverse=True)[:n]
    recent = []
    for date_str in sorted_dates:
        session_rows = workouts_by_date[date_str]
        workout_name = session_rows[0].get("Workout Name", "")
        exercises_in_session = defaultdict(list)
        for r in session_rows:
            exercises_in_session[r.get("Exercise Name", "Unknown")].append({
                "set": r.get("Set Order"),
                "weight": r.get("Weight"),
                "reps": r.get("Reps"),
                "distance": r.get("Distance"),
                "seconds": r.get("Seconds"),
                "rpe": r.get("RPE"),
            })
        recent.append({
            "date": date_str,
            "workout_name": workout_name,
            "duration": session_rows[0].get("Duration", ""),
            "exercises": dict(exercises_in_session),
        })
    return recent


def progression_data(rows: list[dict], exercise_name: str) -> list[dict]:
    """Return per-session best set (heaviest weight) for a given exercise."""
    sessions = defaultdict(list)
    for row in rows:
        if row.get("Exercise Name", "").lower() == exercise_name.lower():
            date = row.get("Date")
            date_key = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10]
            sessions[date_key].append(row)

    progression = []
    for date_str in sorted(sessions.keys()):
        best = max(sessions[date_str], key=lambda r: (r.get("Weight") or 0))
        progression.append({
            "date": date_str,
            "weight": best.get("Weight"),
            "reps": best.get("Reps"),
            "estimated_1rm": _estimated_1rm(best.get("Weight") or 0, best.get("Reps") or 0),
        })
    return progression


def _estimated_1rm(weight: float, reps: int) -> float:
    """Epley formula for estimated one-rep max."""
    if reps <= 0 or weight <= 0:
        return 0
    if reps == 1:
        return weight
    return round(weight * (1 + reps / 30), 1)
