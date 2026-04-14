# Strong App Workout Analyzer

Analyze your [Strong](https://www.strong.app/) workout exports using Claude AI.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
```

## Export your data from Strong

1. Open the Strong app
2. Go to **Settings → Export Data**
3. Save the CSV file (e.g. `strong_workouts.csv`)

## Usage

```bash
# Full AI analysis
python -m strong_analyzer ~/Downloads/strong_workouts.csv

# Ask a specific question
python -m strong_analyzer ~/Downloads/strong_workouts.csv --ask "Am I overtraining chest?"

# Track specific exercise progressions
python -m strong_analyzer ~/Downloads/strong_workouts.csv --track "Bench Press" --track "Squat"

# List all exercises in your data
python -m strong_analyzer ~/Downloads/strong_workouts.csv --list-exercises

# Dump parsed data as JSON (no API call)
python -m strong_analyzer ~/Downloads/strong_workouts.csv --summary-only
```

## What Claude analyzes

- **Training volume & frequency** - consistency, sessions per week
- **Strength progressions** - exercises trending up, plateaued, or declining
- **Programming balance** - muscle group coverage, push/pull ratios
- **Recovery signals** - signs of overtraining from performance data
- **Estimated 1RMs** - calculated via the Epley formula
- **Actionable recommendations** - specific next steps to improve
