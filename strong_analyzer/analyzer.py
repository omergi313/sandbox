"""Send parsed Strong data to Claude for workout analysis."""

import json

import anthropic

SYSTEM_PROMPT = """\
You are an expert strength and conditioning coach with deep knowledge of \
exercise science, periodization, and progressive overload. You analyze workout \
data exported from the Strong app.

When analyzing data, provide:
1. **Training Overview** - Volume, frequency, consistency assessment
2. **Strength Progress** - Identify exercises trending up, plateaued, or declining
3. **Programming Insights** - Muscle balance, exercise selection, set/rep patterns
4. **Recovery Signals** - Signs of overtraining or undertraining from the data
5. **Actionable Recommendations** - Specific, numbered suggestions to improve

Be concise and data-driven. Reference specific numbers from the data. \
Use strength training terminology appropriately. If data is limited, say so \
rather than speculating."""


def analyze_workouts(
    summary: dict,
    recent_workouts: list[dict],
    progressions: dict[str, list[dict]] | None = None,
    user_question: str | None = None,
) -> str:
    """Send workout data to Claude and return the analysis."""
    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var

    data_block = json.dumps(
        {
            "overall_summary": summary,
            "recent_workouts": recent_workouts,
            "exercise_progressions": progressions or {},
        },
        indent=2,
        default=str,
    )

    user_message = f"Here is my Strong app workout data:\n\n```json\n{data_block}\n```\n\n"
    if user_question:
        user_message += f"My specific question: {user_question}"
    else:
        user_message += (
            "Please provide a comprehensive analysis of my training. "
            "Identify strengths, weaknesses, and give me actionable recommendations."
        )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def ask_about_workouts(
    summary: dict,
    recent_workouts: list[dict],
    question: str,
    progressions: dict[str, list[dict]] | None = None,
) -> str:
    """Ask a specific question about your workout data."""
    return analyze_workouts(summary, recent_workouts, progressions, user_question=question)
