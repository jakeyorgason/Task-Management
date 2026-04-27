from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from clickup_client import PRIORITY_LABELS, ms_to_datetime


def _names(items: Optional[List[Dict[str, Any]]], key: str = "username") -> str:
    if not items:
        return ""
    names = []
    for item in items:
        names.append(item.get(key) or item.get("email") or item.get("id") or "")
    return ", ".join([str(x) for x in names if x])


def normalize_tasks(tasks: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []

    for task in tasks:
        due_dt = ms_to_datetime(task.get("due_date"))
        updated_dt = ms_to_datetime(task.get("date_updated"))
        created_dt = ms_to_datetime(task.get("date_created"))

        priority_obj = task.get("priority") or {}
        priority_id = priority_obj.get("id")
        try:
            priority_id = int(priority_id) if priority_id is not None else None
        except Exception:
            priority_id = None

        status_obj = task.get("status") or {}
        list_obj = task.get("list") or {}
        folder_obj = task.get("folder") or {}
        space_obj = task.get("space") or {}

        rows.append(
            {
                "id": task.get("id"),
                "custom_id": task.get("custom_id"),
                "name": task.get("name", ""),
                "status": status_obj.get("status", ""),
                "status_color": status_obj.get("color", ""),
                "priority": PRIORITY_LABELS.get(priority_id, "None"),
                "priority_id": priority_id,
                "due": due_dt.date() if due_dt else None,
                "due_datetime": due_dt,
                "created": created_dt,
                "updated": updated_dt,
                "url": task.get("url", ""),
                "description": task.get("markdown_description") or task.get("description") or "",
                "assignees": _names(task.get("assignees")),
                "list": list_obj.get("name", ""),
                "list_id": str(list_obj.get("id", "") or ""),
                "folder": folder_obj.get("name", ""),
                "folder_id": str(folder_obj.get("id", "") or ""),
                "space": space_obj.get("name", ""),
                "space_id": str(space_obj.get("id", "") or ""),
                "tags": ", ".join([tag.get("name", "") for tag in task.get("tags", []) if tag.get("name")]),
                "raw": task,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "id",
                "name",
                "status",
                "priority",
                "due",
                "updated",
                "url",
                "assignees",
                "list",
                "list_id",
                "folder",
                "folder_id",
                "space",
                "space_id",
                "tags",
                "description",
                "raw",
            ]
        )

    today = date.today()
    df["is_overdue"] = df["due"].apply(lambda x: bool(x and x < today))
    df["is_due_today"] = df["due"].apply(lambda x: bool(x and x == today))
    df["is_due_this_week"] = df["due"].apply(lambda x: bool(x and today <= x <= today + timedelta(days=7)))
    df["has_no_due_date"] = df["due"].isna()
    df["days_until_due"] = df["due"].apply(lambda x: (x - today).days if x else None)

    return df


def filter_tasks(
    df: pd.DataFrame,
    *,
    search: str = "",
    statuses: Optional[List[str]] = None,
    priorities: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None,
    lists: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    filtered = df.copy()

    if search.strip():
        s = search.strip().lower()
        text_cols = ["name", "description", "list", "folder", "space", "tags", "assignees"]
        mask = False
        for col in text_cols:
            mask = mask | filtered[col].fillna("").str.lower().str.contains(s, regex=False)
        filtered = filtered[mask]

    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]

    if priorities:
        filtered = filtered[filtered["priority"].isin(priorities)]

    if assignees:
        assignee_mask = False
        for assignee in assignees:
            assignee_mask = assignee_mask | filtered["assignees"].fillna("").str.contains(assignee, regex=False)
        filtered = filtered[assignee_mask]

    if lists:
        filtered = filtered[filtered["list"].isin(lists)]

    if tags:
        tag_mask = False
        for tag in tags:
            tag_mask = tag_mask | filtered["tags"].fillna("").str.contains(tag, regex=False)
        filtered = filtered[tag_mask]

    priority_sort = {"Urgent": 1, "High": 2, "Normal": 3, "Low": 4, "None": 5}
    filtered["_priority_sort"] = filtered["priority"].map(priority_sort).fillna(9)
    filtered["_due_sort"] = pd.to_datetime(filtered["due"], errors="coerce")
    filtered = filtered.sort_values(["_due_sort", "_priority_sort", "updated"], ascending=[True, True, False], na_position="last")
    return filtered.drop(columns=["_priority_sort", "_due_sort"], errors="ignore")


def metric_counts(df: pd.DataFrame) -> Dict[str, int]:
    if df.empty:
        return {"total": 0, "overdue": 0, "today": 0, "week": 0, "no_due": 0}
    return {
        "total": int(len(df)),
        "overdue": int(df["is_overdue"].sum()),
        "today": int(df["is_due_today"].sum()),
        "week": int(df["is_due_this_week"].sum()),
        "no_due": int(df["has_no_due_date"].sum()),
    }
