from __future__ import annotations

import os
from typing import Optional

import pandas as pd


def build_task_brief(df: pd.DataFrame) -> str:
    if df.empty:
        return "No tasks found for the current filters."

    rows = []
    for _, row in df.head(40).iterrows():
        rows.append(
            f"- {row.get('name')} | status={row.get('status')} | priority={row.get('priority')} | "
            f"due={row.get('due')} | list={row.get('list')} | assignees={row.get('assignees')} | url={row.get('url')}"
        )
    return "\n".join(rows)


def get_ai_daily_brief(df: pd.DataFrame, api_key: Optional[str], model: str = "gpt-5.5-thinking") -> str:
    if not api_key:
        return "Add OPENAI_API_KEY to enable the AI daily brief."

    try:
        from openai import OpenAI
    except Exception:
        return "The OpenAI package is not installed. Run `pip install openai`."

    client = OpenAI(api_key=api_key)

    prompt = f"""
You are helping an ecommerce account manager plan their workday.

Use the task list below to create:
1. The top 5 tasks to prioritize today
2. Any overdue or risky tasks
3. Quick wins
4. A suggested work sequence

Be direct, practical, and concise. Do not invent tasks.

Tasks:
{build_task_brief(df)}
""".strip()

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
        )
        return response.output_text
    except Exception as exc:
        return f"AI brief failed: {exc}"
