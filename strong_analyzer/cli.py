"""CLI entry point for Strong workout analyzer."""

import argparse
import json
import sys

from .parser import build_summary, load_csv, progression_data, recent_workouts_detail


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Strong app workout exports with Claude AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Full analysis of your workouts
  python -m strong_analyzer /Users/ogindes/Downloads/strong_workouts.csv

  # Ask a specific question
  python -m strong_analyzer workouts.csv --ask "Am I overtraining chest?"

  # Track progression for specific exercises
  python -m strong_analyzer workouts.csv --track "Bench Press" --track "Squat"

  # Just dump parsed summary (no Claude API call)
  python -m strong_analyzer workouts.csv --summary-only

  # Include more recent workout detail
  python -m strong_analyzer workouts.csv --recent 20
""",
    )
    parser.add_argument("csv_path", help="Path to Strong app CSV export")
    parser.add_argument("--ask", "-a", help="Ask a specific question about your workouts")
    parser.add_argument(
        "--track",
        "-t",
        action="append",
        default=[],
        help="Track progression for specific exercise(s). Can be repeated.",
    )
    parser.add_argument(
        "--recent",
        "-r",
        type=int,
        default=10,
        help="Number of recent workouts to include (default: 10)",
    )
    parser.add_argument(
        "--summary-only",
        "-s",
        action="store_true",
        help="Print parsed summary as JSON without calling Claude",
    )
    parser.add_argument(
        "--list-exercises",
        "-l",
        action="store_true",
        help="List all exercise names found in the CSV",
    )

    args = parser.parse_args()

    # Load and parse
    try:
        rows = load_csv(args.csv_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print("Error: CSV file is empty or has no valid data.", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(rows)} sets from Strong export.\n")

    # List exercises mode
    if args.list_exercises:
        exercises = sorted({r.get("Exercise Name", "Unknown") for r in rows})
        print("Exercises found:")
        for ex in exercises:
            print(f"  - {ex}")
        return

    # Build data
    summary = build_summary(rows)
    recent = recent_workouts_detail(rows, n=args.recent)

    # Build progressions for tracked exercises
    progressions = {}
    for exercise in args.track:
        prog = progression_data(rows, exercise)
        if prog:
            progressions[exercise] = prog
        else:
            print(f"Warning: No data found for exercise '{exercise}'", file=sys.stderr)

    # If no explicit tracks, auto-track top 5 exercises by set count
    if not args.track:
        top_exercises = sorted(summary["exercises"], key=lambda e: e["total_sets"], reverse=True)[:5]
        for ex_info in top_exercises:
            prog = progression_data(rows, ex_info["exercise"])
            if prog:
                progressions[ex_info["exercise"]] = prog

    # Summary-only mode
    if args.summary_only:
        output = {
            "summary": summary,
            "recent_workouts": recent,
            "progressions": progressions,
        }
        print(json.dumps(output, indent=2, default=str))
        return

    # Call Claude for analysis
    try:
        from .analyzer import analyze_workouts, ask_about_workouts
    except ImportError:
        print(
            "Error: anthropic package not installed. Run: pip install anthropic",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Sending data to Claude for analysis...\n")
    print("=" * 60)

    if args.ask:
        result = ask_about_workouts(summary, recent, args.ask, progressions)
    else:
        result = analyze_workouts(summary, recent, progressions)

    print(result)
    print("=" * 60)


if __name__ == "__main__":
    main()
