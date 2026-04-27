from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from ai_summary import get_ai_daily_brief
from clickup_client import ClickUpClient, ClickUpConfig, PRIORITY_VALUES, date_to_clickup_ms
from task_processing import filter_tasks, metric_counts, normalize_tasks

st.set_page_config(
    page_title="Evolved Commerce ClickUp Command Center",
    page_icon="✅",
    layout="wide",
)

USER_DISPLAY_ORDER = [
    "All Users",
    "Accounting",
    "Audrey Walker",
    "Beau Jensen",
    "Brock Arbon",
    "Bryan Bateman",
    "Cameron Meador",
    "Dallin Lindsey",
    "Distribution Account Management",
    "Distribution Operations",
    "Donny Harding",
    "Gabriel Kalt",
    "Isaac Johnson",
    "Jake Yorgason",
    "James Maxwell",
    "Kee Jensen",
    "Kensie Gomer",
    "Kyle Buhler",
    "Kyle Rutland",
    "Liberty Lighten",
    "Management",
    "Matson Tolman",
    "OPS",
    "Quinn Meador",
    "Sales",
    "Skyler Jensen",
    
]

# Maps your full user names in Streamlit Secrets to the Space names in the uploaded folder reference.
# If a person does not have a matching space in clickup_folder_ids.csv, the app falls back to task-derived folders.
PERSON_SPACE_NAME_MAP = {
    "Jake Yorgason": "Jake",
    "Audrey Walker": "Audrey",
    "Beau Jensen": "Beau",
    "Brock Arbon": "Brock",
    "Brock Bolen": "Brock",
    "Bryan Bateman": "Bryan's Team",
    "Cameron Meador": "Cameron",
    "Dallin Lindsey": "Dallin",
    "Donny Harding": "Donny",
    "Gabriel Kalt": "Gabriel K.",
    "Isaac Johnson": "Isaac",
    "James Maxwell": "James",
    "Kee Jensen": "Kee",
    "Kensie Gomer": "Kensie",
    "Kyle Buhler": "Kyle B.",
    "Kyle Rutland": "Rutland",
    "Liberty Lighten": "Liberty",
    "Matson Tolman": "Matson",
    "Quinn Meador": "Quinn",
    "Skyler Jensen": "Skyler",
}

st.markdown(
    """
    <style>
        html, body, [data-testid="stAppViewContainer"], .stApp { background: #FFFFFF !important; color: #111827 !important; }
        [data-testid="stHeader"], [data-testid="stToolbar"] { background: #FFFFFF !important; }
        [data-testid="stSidebar"] { background: #F5F5F5 !important; color: #111827 !important; }
        [data-testid="stSidebar"] * { color: #111827 !important; }
        .main > div, .block-container { background: #FFFFFF !important; }
        .block-container { padding-top: 1rem; padding-bottom: 1.5rem; max-width: 1460px; }
        div[data-baseweb="select"] > div, div[data-baseweb="input"] input, textarea, [data-testid="stTextInput"] input { background-color: #FFFFFF !important; color: #111827 !important; border-color: #D1D5DB !important; }
        [data-testid="stMultiSelect"] div { color: #111827 !important; }
        .brand-shell { background: linear-gradient(135deg, #EA580C 0%, #1F2937 100%); border-radius: 22px; padding: 52px 32px; color: white; margin-bottom: 1.1rem; box-shadow: 0 12px 28px rgba(0,0,0,.12); }
        .brand-title { font-size: 2.2rem; font-weight: 850; line-height: 1.05; margin: 0; letter-spacing: -0.02em; }
        .brand-subtitle { font-size: 1rem; opacity: .96; margin-top: .7rem; max-width: 900px; }
        .section-title { font-size: 1.22rem; font-weight: 780; color: #111827; margin-bottom: .18rem; }
        .section-note { color: #4B5563; font-size: .94rem; margin-bottom: .9rem; }
        .section-divider { border-top: 1px solid #E5E7EB; margin: 1.1rem 0 1.2rem 0; }
        .metric-card { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 14px 15px; box-shadow: 0 4px 14px rgba(15,23,42,.05); min-height: 84px; }
        .metric-label { font-size: .75rem; color: #6B7280; margin-bottom: .3rem; font-weight: 650; }
        .metric-value { font-size: 1.65rem; line-height: 1.1; font-weight: 850; color: #1F2937; word-break: break-word; }
        .metric-card.good { border-left: 5px solid #10B981; } .metric-card.warn { border-left: 5px solid #F59E0B; } .metric-card.bad { border-left: 5px solid #EF4444; } .metric-card.brand { border-left: 5px solid #F97316; } .metric-card.neutral { border-left: 5px solid #6B7280; }
        .info-banner { background: #FFF7ED; border: 1px solid #F97316; border-left: 6px solid #F97316; border-radius: 15px; padding: 14px 16px; margin: 0.4rem 0 1rem 0; }
        .info-banner-title { font-weight: 850; color: #111827; margin-bottom: 4px; }
        .info-banner-body { color: #374151; font-size: .94rem; }
        .control-panel { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 18px; padding: 18px 18px 10px 18px; box-shadow: 0 6px 20px rgba(15,23,42,.055); margin-bottom: 1rem; }
        .client-card, .task-card { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px; padding: 15px 16px; box-shadow: 0 4px 14px rgba(15,23,42,.045); margin-bottom: .75rem; }
        .client-name { color: #111827; font-size: 1.02rem; font-weight: 820; margin-bottom: 7px; }
        .client-stat, .task-meta { color: #4B5563; font-size: .88rem; margin-bottom: 3px; }
        .task-title { font-size: 1.05rem; font-weight: 820; color: #111827; margin-bottom: 4px; }
        .footer-note { color: #6B7280; font-size: .85rem; text-align: center; opacity: .9; margin-top: .35rem; margin-bottom: .5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
        if value is None:
            return default
        return str(value).strip()
    except Exception:
        return os.getenv(name, default).strip()


def get_secret_table(name: str) -> Dict[str, str]:
    try:
        table = st.secrets.get(name, {})
        if not table:
            return {}
        return {str(k).strip(): str(v).strip() for k, v in table.items()}
    except Exception:
        return {}


def get_clickup_users() -> Dict[str, str]:
    return get_secret_table("CLICKUP_USERS")


def get_clickup_create_lists() -> Dict[str, str]:
    return get_secret_table("CLICKUP_CREATE_LISTS")


def split_ids(value: str) -> List[str]:
    return [x.strip() for x in str(value or "").split(",") if x.strip()]


def safe_int(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def ordered_user_options(clickup_users: Dict[str, str]) -> List[str]:
    if not clickup_users:
        return ["All Users"]
    ordered = [name for name in USER_DISPLAY_ORDER if name in clickup_users]
    extras = sorted([name for name in clickup_users.keys() if name not in ordered])
    options = ordered + extras
    if "All Users" not in options:
        options = ["All Users"] + options
    return options


@st.cache_data(ttl=900, show_spinner=False)
def load_folder_reference() -> pd.DataFrame:
    paths = [
        Path("clickup_folder_ids.csv"),
        Path("data/clickup_folder_ids.csv"),
        Path("assets/clickup_folder_ids.csv"),
    ]
    for path in paths:
        if path.exists():
            df = pd.read_csv(path, dtype=str).fillna("")
            expected = {"space_name", "space_id", "folder_name", "folder_id"}
            if expected.issubset(set(df.columns)):
                for col in expected:
                    df[col] = df[col].astype(str).str.strip()
                return df.sort_values(["space_name", "folder_name"]).reset_index(drop=True)
    return pd.DataFrame(columns=["space_name", "space_id", "folder_name", "folder_id"])


def resolve_space_for_user(selected_user: str, folder_ref: pd.DataFrame) -> Tuple[str, str]:
    if selected_user == "All Users" or folder_ref.empty:
        return "", ""

    candidate_names = [
        PERSON_SPACE_NAME_MAP.get(selected_user, ""),
        selected_user,
        selected_user.split(" ")[0] if selected_user else "",
    ]
    candidate_names = [x for x in candidate_names if x]

    for candidate in candidate_names:
        match = folder_ref[folder_ref["space_name"].str.lower() == candidate.lower()]
        if not match.empty:
            return str(match.iloc[0]["space_name"]), str(match.iloc[0]["space_id"])

    return "", ""


def get_unique_values(df: pd.DataFrame, col: str) -> List[str]:
    if df.empty or col not in df.columns:
        return []
    return sorted([str(x) for x in df[col].dropna().unique().tolist() if str(x).strip()])


def render_metric_card(label: str, value: str, tone: str = "brand") -> None:
    st.markdown(
        f"""
        <div class="metric-card {tone}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_info_banner(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="info-banner">
            <div class="info-banner-title">{title}</div>
            <div class="info-banner-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=180, show_spinner=False)
def load_tasks(api_token: str, team_id: str, list_ids: str, assignee_ids: str, include_closed: bool, page_limit: int):
    client = ClickUpClient(
        ClickUpConfig(
            api_token=api_token,
            team_id=team_id,
            list_ids=split_ids(list_ids),
            assignee_ids=split_ids(assignee_ids),
        )
    )
    return client.get_filtered_team_tasks(include_closed=include_closed, page_limit=page_limit)


def get_client() -> ClickUpClient:
    return ClickUpClient(
        ClickUpConfig(
            api_token=get_secret("CLICKUP_API_TOKEN"),
            team_id=get_secret("CLICKUP_TEAM_ID"),
            list_ids=split_ids(get_secret("CLICKUP_LIST_IDS")),
            assignee_ids=split_ids(get_secret("CLICKUP_ASSIGNEE_IDS")),
        )
    )


def get_list_options_from_tasks(df: pd.DataFrame) -> Dict[str, str]:
    options: Dict[str, str] = {}
    if df.empty:
        return options
    required_cols = {"space", "folder", "list", "list_id"}
    if not required_cols.issubset(set(df.columns)):
        return options
    for _, row in df.iterrows():
        list_id = str(row.get("list_id") or "").strip()
        if not list_id:
            continue
        parts = [str(row.get(c) or "").strip() for c in ["space", "folder", "list"]]
        label = " / ".join([x for x in parts if x]) or list_id
        options[label] = list_id
    return dict(sorted(options.items(), key=lambda item: item[0].lower()))


def render_header() -> None:
    st.markdown(
        """
        <div class="brand-shell">
            <div class="brand-title">Evolved Commerce<br>ClickUp Command Center</div>
            <div class="brand-subtitle">Cleaner task visibility • Client folders • Due date focus • Status updates • Comments • Task creation • AI daily planning</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_info_banner(
        "Folder ID mapping added",
        "The Client / Folder picker now uses your ClickUp folder reference CSV, so selected people show the folders from their actual ClickUp space instead of only folders found in loaded tasks.",
    )


def render_user_panel(clickup_users: Dict[str, str], fallback_assignee_ids: str, folder_ref: pd.DataFrame):
    st.markdown('<div class="section-title">Workspace View</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-note">Choose a person. The app maps that person to their ClickUp space and folder IDs when available.</div>', unsafe_allow_html=True)
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    selected_user = st.selectbox("Person / Space", ordered_user_options(clickup_users), index=0)
    st.markdown('</div>', unsafe_allow_html=True)

    if selected_user == "All Users":
        selected_assignee_ids = ""
    else:
        selected_assignee_ids = clickup_users.get(selected_user, "")

    if not clickup_users:
        selected_user = "Default Assignee Filter" if fallback_assignee_ids else "All Users"
        selected_assignee_ids = fallback_assignee_ids

    selected_space_name, selected_space_id = resolve_space_for_user(selected_user, folder_ref)
    return {
        "selected_user": selected_user,
        "selected_assignee_ids": selected_assignee_ids,
        "selected_space_name": selected_space_name,
        "selected_space_id": selected_space_id,
    }


def folder_options_for_space(df: pd.DataFrame, folder_ref: pd.DataFrame, selected_space_id: str, selected_user: str) -> Dict[str, str]:
    options: Dict[str, str] = {}

    if not folder_ref.empty:
        ref = folder_ref.copy()
        if selected_space_id:
            ref = ref[ref["space_id"] == selected_space_id]
        for _, row in ref.iterrows():
            folder_name = str(row.get("folder_name") or "").strip()
            folder_id = str(row.get("folder_id") or "").strip()
            space_name = str(row.get("space_name") or "").strip()
            if not folder_name or not folder_id:
                continue
            label = folder_name if selected_user != "All Users" else f"{space_name} / {folder_name}"
            options[label] = folder_id

    # Fallback/additions from loaded tasks, useful when the CSV is missing a new folder.
    if not df.empty and {"folder", "folder_id", "space"}.issubset(df.columns):
        task_df = df.copy()
        if selected_space_id and "space_id" in task_df.columns:
            task_df = task_df[task_df["space_id"].astype(str) == selected_space_id]
        for _, row in task_df.iterrows():
            folder_name = str(row.get("folder") or "").strip()
            folder_id = str(row.get("folder_id") or "").strip()
            space_name = str(row.get("space") or "").strip()
            if not folder_name:
                continue
            label = folder_name if selected_user != "All Users" else f"{space_name} / {folder_name}"
            options.setdefault(label, folder_id or folder_name)

    return dict(sorted(options.items(), key=lambda item: item[0].lower()))


def render_filter_panel(df: pd.DataFrame, folder_ref: pd.DataFrame, selected_space_id: str, selected_user: str):
    st.markdown('<div class="section-title">Task Filters</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-note">Client / Folder options come from the folder ID reference for the selected space.</div>', unsafe_allow_html=True)
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)

    folder_options = folder_options_for_space(df, folder_ref, selected_space_id, selected_user)
    top1, top2 = st.columns([1.2, 1.8])
    with top1:
        selected_folder_labels = st.multiselect("Client / Folder", list(folder_options.keys()))
    with top2:
        search = st.text_input("Search", placeholder="task, client, tag, assignee, description...")

    bottom1, bottom2, bottom3, bottom4 = st.columns(4)
    with bottom1:
        selected_lists = st.multiselect("Task List", get_unique_values(df, "list"))
    with bottom2:
        selected_statuses = st.multiselect("Status", get_unique_values(df, "status"))
    with bottom3:
        selected_priorities = st.multiselect("Priority", ["Urgent", "High", "Normal", "Low", "None"])
    with bottom4:
        assignee_values = sorted({name.strip() for names in df.get("assignees", pd.Series(dtype=str)).dropna().tolist() for name in str(names).split(",") if name.strip()})
        selected_assignees = st.multiselect("Assignee", assignee_values)

    tag_values = sorted({tag.strip() for tags in df.get("tags", pd.Series(dtype=str)).dropna().tolist() for tag in str(tags).split(",") if tag.strip()})
    with st.expander("More filters", expanded=False):
        selected_tags = st.multiselect("Tags", tag_values)
        card_limit = st.slider("Task cards to show", min_value=5, max_value=60, value=18, step=5)

    st.markdown('</div>', unsafe_allow_html=True)

    return {
        "selected_folder_labels": selected_folder_labels,
        "selected_folder_ids": [folder_options[label] for label in selected_folder_labels],
        "selected_lists": selected_lists,
        "selected_statuses": selected_statuses,
        "selected_priorities": selected_priorities,
        "selected_assignees": selected_assignees,
        "selected_tags": selected_tags,
        "search": search,
        "card_limit": card_limit,
        "folder_options": folder_options,
    }


def apply_main_filters(df: pd.DataFrame, filter_state: Dict, selected_space_id: str) -> pd.DataFrame:
    base = df.copy()
    if selected_space_id and "space_id" in base.columns:
        base = base[base["space_id"].astype(str) == str(selected_space_id)]

    filtered = filter_tasks(
        base,
        search=filter_state["search"],
        statuses=filter_state["selected_statuses"],
        priorities=filter_state["selected_priorities"],
        assignees=filter_state["selected_assignees"],
        lists=filter_state["selected_lists"],
        tags=filter_state["selected_tags"],
    )

    selected_folder_ids = [str(x) for x in filter_state["selected_folder_ids"] if str(x).strip()]
    if selected_folder_ids and not filtered.empty:
        if "folder_id" in filtered.columns:
            filtered = filtered[filtered["folder_id"].astype(str).isin(selected_folder_ids)]
        else:
            selected_names = [label.split(" / ")[-1] for label in filter_state["selected_folder_labels"]]
            filtered = filtered[filtered["folder"].isin(selected_names)]

    return filtered


def render_summary_metrics(filtered: pd.DataFrame) -> None:
    counts = metric_counts(filtered)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: render_metric_card("Visible Tasks", str(counts["total"]), "brand")
    with c2: render_metric_card("Overdue", str(counts["overdue"]), "bad" if counts["overdue"] else "good")
    with c3: render_metric_card("Due Today", str(counts["today"]), "warn" if counts["today"] else "good")
    with c4: render_metric_card("Due This Week", str(counts["week"]), "brand")
    with c5: render_metric_card("No Due Date", str(counts["no_due"]), "neutral" if counts["no_due"] else "good")


def render_task_cards(df: pd.DataFrame, limit: int = 12):
    if df.empty:
        st.info("No matching tasks.")
        return
    for _, row in df.head(limit).iterrows():
        overdue = bool(row.get("is_overdue"))
        due_text = row.get("due") or "No due date"
        task_url = row.get("url") or ""
        task_name = row.get("name") or "Untitled Task"
        badge = "🔴 Overdue" if overdue else "🟢 Open"
        st.markdown('<div class="task-card">', unsafe_allow_html=True)
        if task_url:
            st.markdown(f'<div class="task-title"><a href="{task_url}" target="_blank">{task_name}</a></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="task-title">{task_name}</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="task-meta">{badge} · <b>Status:</b> {row.get('status') or 'None'} · <b>Priority:</b> {row.get('priority') or 'None'} · <b>Due:</b> {due_text}</div>
            <div class="task-meta"><b>Client:</b> {row.get('folder') or 'No Client / Folder'} · <b>Folder ID:</b> {row.get('folder_id') or '-'} · <b>Task List:</b> {row.get('list') or '-'} · <b>Space:</b> {row.get('space') or '-'}</div>
            """,
            unsafe_allow_html=True,
        )
        if row.get("assignees"):
            st.caption(f"Assignees: {row.get('assignees')}")
        if row.get("description"):
            with st.expander("Description preview"):
                st.write(str(row.get("description"))[:1200])
        st.markdown('</div>', unsafe_allow_html=True)


def render_task_table(df: pd.DataFrame, title: str):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if df.empty:
        st.info("No tasks found here.")
        return
    display_cols = ["name", "folder", "folder_id", "list", "status", "priority", "due", "assignees", "space", "space_id", "tags", "url"]
    shown = df[[c for c in display_cols if c in df.columns]].copy()
    shown = shown.rename(columns={"name":"Task","folder":"Client","folder_id":"Folder ID","list":"Task List","space":"Person Space","space_id":"Space ID","status":"Status","priority":"Priority","due":"Due","assignees":"Assignees","tags":"Tags","url":"ClickUp"})
    st.dataframe(shown, use_container_width=True, hide_index=True, height=520, column_config={"ClickUp": st.column_config.LinkColumn("ClickUp"), "Due": st.column_config.DateColumn("Due")})


def render_client_overview(filtered: pd.DataFrame, folder_ref: pd.DataFrame, selected_space_id: str, card_limit: int):
    st.markdown('<div class="section-title">Client Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-note">Shows folder IDs and task counts for the selected space/client set.</div>', unsafe_allow_html=True)

    if not folder_ref.empty and selected_space_id:
        folders = folder_ref[folder_ref["space_id"] == selected_space_id].copy()
    else:
        folders = pd.DataFrame(columns=["space_name", "space_id", "folder_name", "folder_id"])

    if filtered.empty and folders.empty:
        st.info("No folders or tasks found for the current filters.")
        return

    counts = pd.DataFrame()
    if not filtered.empty and "folder_id" in filtered.columns:
        counts = (
            filtered.groupby(["folder_id", "folder"], dropna=False)
            .agg(total_tasks=("id", "count"), overdue=("is_overdue", "sum"), due_today=("is_due_today", "sum"), due_this_week=("is_due_this_week", "sum"))
            .reset_index()
        )

    if not folders.empty:
        summary = folders.rename(columns={"folder_name": "Client", "folder_id": "Folder ID", "space_name": "Space", "space_id": "Space ID"})
        if not counts.empty:
            summary = summary.merge(counts, left_on="Folder ID", right_on="folder_id", how="left")
        for col in ["total_tasks", "overdue", "due_today", "due_this_week"]:
            if col not in summary.columns:
                summary[col] = 0
            summary[col] = summary[col].fillna(0).astype(int)
    else:
        summary = counts.rename(columns={"folder": "Client", "folder_id": "Folder ID"})
        summary["Space"] = ""
        summary["Space ID"] = ""

    summary = summary.sort_values(["overdue", "due_today", "due_this_week", "total_tasks", "Client"], ascending=[False, False, False, False, True])

    card_cols = st.columns(4)
    for idx, row in summary.head(8).iterrows():
        with card_cols[idx % 4]:
            tone = "#EF4444" if int(row.get("overdue", 0)) else "#F97316"
            st.markdown(
                f"""
                <div class="client-card" style="border-left:5px solid {tone};">
                    <div class="client-name">{row.get('Client', 'No Client')}</div>
                    <div class="client-stat"><b>Folder ID:</b> {row.get('Folder ID', '-')}</div>
                    <div class="client-stat"><b>{int(row.get('total_tasks', 0))}</b> visible tasks</div>
                    <div class="client-stat"><b>{int(row.get('overdue', 0))}</b> overdue</div>
                    <div class="client-stat"><b>{int(row.get('due_this_week', 0))}</b> due this week</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.dataframe(summary[[c for c in ["Space", "Space ID", "Client", "Folder ID", "total_tasks", "overdue", "due_today", "due_this_week"] if c in summary.columns]], use_container_width=True, hide_index=True)

    if not summary.empty:
        selected_client = st.selectbox("Inspect client", summary["Client"].tolist())
        selected_folder_ids = summary.loc[summary["Client"] == selected_client, "Folder ID"].astype(str).tolist()
        detail_df = filtered[filtered["folder_id"].astype(str).isin(selected_folder_ids)] if selected_folder_ids and "folder_id" in filtered.columns else filtered[filtered["folder"].eq(selected_client)]
        render_task_cards(detail_df, limit=card_limit)
        render_task_table(detail_df, f"{selected_client} Tasks")


def render_folder_reference_tab(folder_ref: pd.DataFrame):
    st.markdown('<div class="section-title">Folder ID Reference</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-note">Use this table to verify which folders live in which spaces.</div>', unsafe_allow_html=True)
    if folder_ref.empty:
        st.warning("No clickup_folder_ids.csv file found. Add it to your GitHub repo root, data/, or assets/.")
        return
    st.dataframe(folder_ref, use_container_width=True, hide_index=True, height=600)
    st.download_button("Download folder ID reference", data=folder_ref.to_csv(index=False).encode("utf-8"), file_name="clickup_folder_ids.csv", mime="text/csv", use_container_width=True)


def render_team_overview(df: pd.DataFrame):
    st.markdown('<div class="section-title">Team Overview</div>', unsafe_allow_html=True)
    if df.empty:
        st.info("No task data loaded.")
        return
    summary = df.groupby(["space", "space_id"], dropna=False).agg(total_tasks=("id", "count"), overdue=("is_overdue", "sum"), due_today=("is_due_today", "sum"), due_this_week=("is_due_this_week", "sum"), no_due_date=("has_no_due_date", "sum")).reset_index().rename(columns={"space": "Person Space", "space_id": "Space ID"}).sort_values(["overdue", "due_today", "due_this_week", "total_tasks"], ascending=False)
    st.dataframe(summary, use_container_width=True, hide_index=True, height=420)


def render_update_tab(df: pd.DataFrame):
    st.markdown('<div class="section-title">Update a ClickUp Task</div>', unsafe_allow_html=True)
    if df.empty:
        st.info("Load tasks first.")
        return
    task_options = {f"{row['name']} · {row['folder'] or 'No Client'} · {row['status']} · due {row['due'] or 'none'}": row["id"] for _, row in df.iterrows()}
    selected_label = st.selectbox("Choose task", list(task_options.keys()))
    task_id = task_options[selected_label]
    selected = df[df["id"] == task_id].iloc[0]

    with st.form("task_update_form"):
        st.markdown(f"**Selected:** [{selected.get('name')}]({selected.get('url')})" if selected.get("url") else f"**Selected:** {selected.get('name')}")
        st.write(f"**Client:** {selected.get('folder') or '-'} · **Folder ID:** {selected.get('folder_id') or '-'} · **Task List:** {selected.get('list') or '-'}")
        new_name = st.text_input("Task name", value=selected.get("name", ""))
        u4, u5, u6 = st.columns(3)
        with u4:
            new_status = st.text_input("Status", value=selected.get("status", ""), help="Must match a valid status in that ClickUp list.")
        with u5:
            new_priority_label = st.selectbox("Priority", ["Do not change", "Urgent", "High", "Normal", "Low"])
        with u6:
            change_due = st.checkbox("Change due date")
            current_due = selected.get("due")
            new_due = st.date_input("New due date", value=current_due or date.today()) if change_due else None
        change_description = st.checkbox("Replace description")
        new_description = st.text_area("New description", value=str(selected.get("description") or ""), height=160) if change_description else ""
        comment = st.text_area("Add comment", placeholder="Optional comment to add to this task", height=120)
        notify_all = st.checkbox("Notify all task watchers when adding comment", value=False)
        preview = st.form_submit_button("Preview update", type="primary")

    if preview:
        changes = {}
        if new_name != selected.get("name", ""):
            changes["name"] = new_name
        if new_status != selected.get("status", ""):
            changes["status"] = new_status
        if new_priority_label != "Do not change":
            changes["priority"] = PRIORITY_VALUES[new_priority_label]
        if change_due:
            changes["due_date_ms"] = date_to_clickup_ms(new_due)
        if change_description:
            changes["description"] = new_description
        st.session_state["pending_update"] = {"task_id": task_id, "task_name": selected.get("name", ""), "changes": changes, "comment": comment, "notify_all": notify_all}

    pending = st.session_state.get("pending_update")
    if pending:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("### Review before submitting")
        st.json({"task_changes": pending["changes"], "comment": pending["comment"] or None})
        col1, col2 = st.columns([1, 4])
        with col1:
            submit = st.button("Submit to ClickUp", type="primary")
        with col2:
            cancel = st.button("Cancel pending update")
        if cancel:
            st.session_state.pop("pending_update", None)
            st.rerun()
        if submit:
            client = get_client()
            try:
                if pending["changes"]:
                    client.update_task(pending["task_id"], **pending["changes"])
                if pending["comment"].strip():
                    client.add_task_comment(pending["task_id"], pending["comment"], notify_all=bool(pending["notify_all"]))
                st.success("Task updated in ClickUp.")
                st.session_state.pop("pending_update", None)
                st.cache_data.clear()
            except Exception as exc:
                st.error(f"Update failed: {exc}")


def render_create_task_tab(df: pd.DataFrame, clickup_users: Dict[str, str], selected_user: str):
    st.markdown('<div class="section-title">Create a ClickUp Task</div>', unsafe_allow_html=True)
    list_options = get_list_options_from_tasks(df)
    secret_list_options = get_clickup_create_lists()
    combined_list_options = {**list_options, **secret_list_options}
    if not combined_list_options:
        st.info("No ClickUp lists are available yet. Load tasks first, or add [CLICKUP_CREATE_LISTS] in Streamlit Secrets.")
        return
    assignable_users = [u for u in ordered_user_options(clickup_users) if u != "All Users"]
    default_assignees = [selected_user] if selected_user in assignable_users else []

    with st.form("create_task_form"):
        c1, c2 = st.columns([2, 1])
        with c1:
            create_list_label = st.selectbox("Create task in list", list(combined_list_options.keys()))
        with c2:
            priority_label = st.selectbox("Priority", ["None", "Urgent", "High", "Normal", "Low"])
        task_name = st.text_input("Task name")
        task_description = st.text_area("Description", height=160)
        c3, c4, c5 = st.columns(3)
        with c3:
            selected_assignees = st.multiselect("Assign to", assignable_users, default=default_assignees)
        with c4:
            status = st.text_input("Starting status", value="", placeholder="Optional. Must match destination list.")
        with c5:
            add_due_date = st.checkbox("Add due date", value=False)
            due_date = st.date_input("Due date", value=date.today()) if add_due_date else None
        preview_create = st.form_submit_button("Preview new task", type="primary")

    if preview_create:
        assignee_ids = [safe_int(clickup_users.get(name)) for name in selected_assignees]
        assignee_ids = [x for x in assignee_ids if x is not None]
        st.session_state["pending_create"] = {
            "list_label": create_list_label,
            "list_id": combined_list_options[create_list_label],
            "name": task_name.strip(),
            "description": task_description.strip(),
            "assignees": assignee_ids,
            "assignee_names": selected_assignees,
            "status": status.strip(),
            "priority": PRIORITY_VALUES.get(priority_label) if priority_label != "None" else None,
            "priority_label": priority_label,
            "due_date_ms": date_to_clickup_ms(due_date) if add_due_date else None,
            "due_date": str(due_date) if due_date else None,
        }

    pending = st.session_state.get("pending_create")
    if pending:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("### Review before creating")
        st.json({"destination": pending["list_label"], "name": pending["name"], "description": pending["description"] or None, "assignees": pending["assignee_names"], "status": pending["status"] or None, "priority": pending["priority_label"], "due_date": pending["due_date"]})
        col1, col2 = st.columns([1, 4])
        with col1:
            submit_create = st.button("Create in ClickUp", type="primary")
        with col2:
            cancel_create = st.button("Cancel new task")
        if cancel_create:
            st.session_state.pop("pending_create", None)
            st.rerun()
        if submit_create:
            if not pending["name"]:
                st.error("Task name is required.")
                return
            client = get_client()
            try:
                created = client.create_task(pending["list_id"], name=pending["name"], description=pending["description"] or None, assignees=pending["assignees"], status=pending["status"] or None, priority=pending["priority"], due_date_ms=pending["due_date_ms"])
                st.success("Task created in ClickUp.")
                if created.get("url"):
                    st.markdown(f"[Open new task in ClickUp]({created.get('url')})")
                st.session_state.pop("pending_create", None)
                st.cache_data.clear()
            except Exception as exc:
                st.error(f"Task creation failed: {exc}")


def render_ai_brief(filtered: pd.DataFrame):
    st.markdown('<div class="section-title">AI Daily Brief</div>', unsafe_allow_html=True)
    if st.button("Generate AI brief", type="primary"):
        brief = get_ai_daily_brief(filtered, api_key=get_secret("OPENAI_API_KEY"), model=get_secret("OPENAI_MODEL", "gpt-5.5"))
        st.markdown(brief)


with st.sidebar:
    st.markdown("## Tool Guide")
    st.markdown("""
**What this tool does**
- Pulls ClickUp tasks by person/space
- Uses folder IDs for client/folder mapping
- Shows due, overdue, and priority work
- Lets you update task status, priority, due date, and comments
- Lets you create new ClickUp tasks
""")
    st.markdown("---")
    st.markdown("## Data Settings")
    include_closed = st.checkbox("Include closed tasks", value=False)
    page_limit = st.number_input("Max ClickUp pages", min_value=1, max_value=50, value=10, step=1)
    refresh_clicked = st.button("Refresh ClickUp Data", use_container_width=True)
    st.markdown("---")
    st.markdown("## App Info")
    st.markdown("**App:** ClickUp Command Center")
    st.markdown("**Owner:** Jake Yorgason, Evolved Commerce")


def main():
    api_token = get_secret("CLICKUP_API_TOKEN")
    team_id = get_secret("CLICKUP_TEAM_ID")
    list_ids = get_secret("CLICKUP_LIST_IDS")
    fallback_assignee_ids = get_secret("CLICKUP_ASSIGNEE_IDS")
    clickup_users = get_clickup_users()
    folder_ref = load_folder_reference()

    if refresh_clicked:
        st.cache_data.clear()
        st.rerun()

    render_header()

    if not api_token or not team_id:
        st.error("Add CLICKUP_API_TOKEN and CLICKUP_TEAM_ID in Streamlit Cloud Secrets.")
        st.stop()

    user_state = render_user_panel(clickup_users, fallback_assignee_ids, folder_ref)
    selected_user = user_state["selected_user"]
    selected_assignee_ids = user_state["selected_assignee_ids"]
    selected_space_name = user_state["selected_space_name"]
    selected_space_id = user_state["selected_space_id"]


    with st.spinner(f"Loading tasks for {selected_user}..."):
        try:
            raw_tasks = load_tasks(api_token, team_id, list_ids, selected_assignee_ids, include_closed, int(page_limit))
            df = normalize_tasks(raw_tasks)
        except Exception as exc:
            st.error(f"Could not load ClickUp tasks for {selected_user}: {exc}")
            st.stop()

    filter_state = render_filter_panel(df, folder_ref, selected_space_id, selected_user)
    filtered = apply_main_filters(df, filter_state, selected_space_id)

    folder_label = ", ".join(filter_state["selected_folder_labels"]) if filter_state["selected_folder_labels"] else "All Clients"
    space_label = selected_space_name or "All Spaces"
    st.caption(f"Currently viewing: **{selected_user}** · Space: **{space_label}** · Client filter: **{folder_label}**")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    render_summary_metrics(filtered)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    tabs = st.tabs(["Focus Queue", "Client Board", "Today", "This Week", "Overdue", "Team Overview", "All Tasks", "Update Task", "Create Task", "AI Brief", "Admin: Folder IDs"])
    card_limit = filter_state["card_limit"]

    with tabs[0]:
        st.markdown('<div class="section-title">Focus Queue</div>', unsafe_allow_html=True)
        focus = filtered.copy()
        if not focus.empty:
            focus = focus[(focus["is_overdue"]) | (focus["is_due_today"]) | (focus["priority"].isin(["Urgent", "High"]))]
        render_task_cards(focus, limit=card_limit)

    with tabs[1]:
        render_client_overview(filtered, folder_ref, selected_space_id, card_limit)

    with tabs[2]:
        today_df = filtered[filtered["is_due_today"]] if not filtered.empty else filtered
        render_task_cards(today_df, limit=card_limit)
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        render_task_table(today_df, "Today Table")

    with tabs[3]:
        week_df = filtered[filtered["is_due_this_week"]] if not filtered.empty else filtered
        render_task_cards(week_df, limit=card_limit)
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        render_task_table(week_df, "This Week Table")

    with tabs[4]:
        overdue_df = filtered[filtered["is_overdue"]] if not filtered.empty else filtered
        render_task_cards(overdue_df, limit=card_limit)
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        render_task_table(overdue_df, "Overdue Table")

    with tabs[5]:
        render_team_overview(df)

    with tabs[6]:
        render_task_table(filtered, "All Visible Tasks")

    with tabs[7]:
        render_update_tab(filtered)

    with tabs[8]:
        render_create_task_tab(df=filtered if not filtered.empty else df, clickup_users=clickup_users, selected_user=selected_user)

    with tabs[9]:
        render_ai_brief(filtered)

    with tabs[10]:
        render_folder_reference_tab(folder_ref)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([3, 2, 3])
    with c2:
        st.markdown('<div class="footer-note">Evolved Commerce ClickUp Command Center</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
