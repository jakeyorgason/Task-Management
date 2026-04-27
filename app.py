from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from ai_summary import get_ai_daily_brief
from clickup_client import (
    ClickUpClient,
    ClickUpConfig,
    PRIORITY_VALUES,
    date_to_clickup_ms,
)
from task_processing import filter_tasks, metric_counts, normalize_tasks


# =========================================================
# Page config
# =========================================================
st.set_page_config(
    page_title="Evolved Commerce ClickUp Command Center",
    page_icon="✅",
    layout="wide",
)


# =========================================================
# User display order
# =========================================================
USER_DISPLAY_ORDER = [
    "All Users",
    "Jake Yorgason",
    "Aaron Jones",
    "Adan Velasquez",
    "Audrey Walker",
    "Beau Jensen",
    "Brock Arbon",
    "Brock Bolen",
    "Bryan Bateman",
    "Cameron Meador",
    "Chad Accento",
    "Dallin Lindsey",
    "Donny Harding",
    "Gabe Ray",
    "Gabriel Kalt",
    "Isaac Johnson",
    "James Maxwell",
    "Jean Rose S Bistis",
    "Kee Jensen",
    "Kensie Gomer",
    "Kyle Buhler",
    "Kyle Rutland",
    "Liberty Lighten",
    "Matson Tolman",
    "McKenna Confer",
    "Quinn Meador",
    "Ronniel Jayoma",
    "Skyler Jensen",
]


# Optional fallback mapping.
# Your current CSV uses full names for most account-manager spaces, so most users do
# not need a special map. This fallback handles alternate visible names, nicknames,
# and shared/legacy spaces.
DEFAULT_USER_SPACE_MAP = {
    "All Users": "",
    "Jake Yorgason": "Jake Yorgason",
    "Aaron Jones": "Sales",
    "Audrey Walker": "Audrey Walker",
    "Beau Jensen": "Beau Jensen",
    "Brock Arbon": "Brock Arbon",
    "Brock Bolen": "Brock Arbon",
    "Bryan Bateman": "Bryan Bateman",
    "Cameron Meador": "Cameron Meador",
    "Dallin Lindsey": "Dallin Lindsey",
    "Donny Harding": "Donny Harding",
    "Gabriel Kalt": "Gabriel Kalt",
    "Isaac Johnson": "Isaac Johnson",
    "James Maxwell": "James Maxwell",
    "Kee Jensen": "Kee Jensen",
    "Kensie Gomer": "Kensie Gomer",
    "Kyle Buhler": "Kyle Buhler",
    "Kyle Rutland": "Kyle Rutland",
    "Liberty Lighten": "Liberty Lighten",
    "Matson Tolman": "Matson Tolman",
    "Quinn Meador": "Quinn Meador",
    "Skyler Jensen": "Skyler Jensen",
}


# =========================================================
# Styles
# =========================================================
st.markdown(
    """
    <style>
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background: #FFFFFF !important;
            color: #111827 !important;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"] {
            background: #FFFFFF !important;
        }

        [data-testid="stSidebar"] {
            background: #F5F5F5 !important;
            color: #111827 !important;
        }

        [data-testid="stSidebar"] * {
            color: #111827 !important;
        }

        .main > div {
            padding-top: 1rem;
            background: #FFFFFF !important;
        }

        .block-container {
            padding-top: 1rem;
            padding-bottom: 1.5rem;
            max-width: 1460px;
            background: #FFFFFF !important;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] input,
        textarea,
        [data-testid="stTextInput"] input {
            background-color: #FFFFFF !important;
            color: #111827 !important;
            border-color: #D1D5DB !important;
        }

        [data-testid="stMultiSelect"] div {
            color: #111827 !important;
        }

        .brand-shell {
            background: linear-gradient(135deg, #EA580C 0%, #1F2937 100%);
            border-radius: 22px;
            padding: 52px 32px;
            color: white;
            margin-bottom: 1.1rem;
            box-shadow: 0 12px 28px rgba(0,0,0,.12);
        }

        .brand-title {
            font-size: 2.2rem;
            font-weight: 850;
            line-height: 1.05;
            margin: 0;
            letter-spacing: -0.02em;
        }

        .brand-subtitle {
            font-size: 1rem;
            opacity: .96;
            margin-top: .7rem;
            max-width: 900px;
        }

        .section-title {
            font-size: 1.22rem;
            font-weight: 780;
            color: #111827;
            margin-bottom: .18rem;
        }

        .section-note {
            color: #4B5563;
            font-size: .94rem;
            margin-bottom: .9rem;
        }

        .section-divider {
            border-top: 1px solid #E5E7EB;
            margin: 1.1rem 0 1.2rem 0;
        }

        .metric-card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 16px;
            padding: 14px 15px;
            box-shadow: 0 4px 14px rgba(15,23,42,.05);
            min-height: 84px;
        }

        .metric-label {
            font-size: .75rem;
            color: #6B7280;
            margin-bottom: .3rem;
            font-weight: 650;
        }

        .metric-value {
            font-size: 1.65rem;
            line-height: 1.1;
            font-weight: 850;
            color: #1F2937;
            word-break: break-word;
        }

        .metric-value.small {
            font-size: 1.18rem;
        }

        .metric-card.good { border-left: 5px solid #10B981; }
        .metric-card.warn { border-left: 5px solid #F59E0B; }
        .metric-card.bad { border-left: 5px solid #EF4444; }
        .metric-card.brand { border-left: 5px solid #F97316; }
        .metric-card.neutral { border-left: 5px solid #6B7280; }

        .info-banner {
            background: #FFF7ED;
            border: 1px solid #F97316;
            border-left: 6px solid #F97316;
            border-radius: 15px;
            padding: 14px 16px;
            margin: 0.4rem 0 1rem 0;
        }

        .info-banner-title {
            font-weight: 850;
            color: #111827;
            margin-bottom: 4px;
        }

        .info-banner-body {
            color: #374151;
            font-size: .94rem;
        }

        .control-panel {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 18px;
            padding: 18px 18px 10px 18px;
            box-shadow: 0 6px 20px rgba(15,23,42,.055);
            margin-bottom: 1rem;
        }

        .client-card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 16px;
            padding: 14px 15px;
            box-shadow: 0 4px 14px rgba(15,23,42,.045);
            min-height: 116px;
            margin-bottom: .75rem;
        }

        .client-name {
            color: #111827;
            font-size: 1.02rem;
            font-weight: 820;
            margin-bottom: 7px;
        }

        .client-stat {
            color: #4B5563;
            font-size: .88rem;
            margin-bottom: 2px;
        }

        .task-card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 16px;
            padding: 15px 16px;
            box-shadow: 0 4px 14px rgba(15,23,42,.045);
            margin-bottom: .75rem;
        }

        .task-title {
            font-size: 1.05rem;
            font-weight: 820;
            color: #111827;
            margin-bottom: 4px;
        }

        .task-meta {
            color: #6B7280;
            font-size: .86rem;
            margin-bottom: .35rem;
        }

        .footer-note {
            color: #6B7280;
            font-size: .85rem;
            text-align: center;
            opacity: .9;
            margin-top: .35rem;
            margin-bottom: .5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Helpers
# =========================================================
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


def get_user_space_map() -> Dict[str, str]:
    secret_map = get_secret_table("CLICKUP_USER_SPACES")
    merged = DEFAULT_USER_SPACE_MAP.copy()
    merged.update(secret_map)
    return merged


def ordered_user_options(clickup_users: Dict[str, str]) -> List[str]:
    if not clickup_users:
        return ["All Users"]

    ordered = [name for name in USER_DISPLAY_ORDER if name in clickup_users]
    extras = sorted([name for name in clickup_users.keys() if name not in ordered])
    options = ordered + extras

    if "All Users" not in options:
        options = ["All Users"] + options

    return options


def split_ids(value: str) -> List[str]:
    return [x.strip() for x in str(value or "").split(",") if x.strip()]


def safe_int(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def clean_text(value) -> str:
    return " ".join(str(value or "").strip().split())


def get_unique_values(df: pd.DataFrame, col: str) -> List[str]:
    if df.empty or col not in df.columns:
        return []
    return sorted([clean_text(x) for x in df[col].dropna().unique().tolist() if clean_text(x)])


def render_metric_card(label: str, value: str, tone: str = "brand", small: bool = False) -> None:
    value_class = "metric-value small" if small else "metric-value"
    st.markdown(
        f"""
        <div class="metric-card {tone}">
            <div class="metric-label">{label}</div>
            <div class="{value_class}">{value}</div>
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


def display_df(df: pd.DataFrame, height: int = 460) -> None:
    if df is None or df.empty:
        st.info("No data available.")
        return

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    out = out.loc[:, ~pd.Index(out.columns).duplicated(keep="first")].copy()

    st.dataframe(out, use_container_width=True, height=height, hide_index=True)


@st.cache_data(ttl=180, show_spinner=False)
def load_tasks(
    api_token: str,
    team_id: str,
    list_ids: str,
    assignee_ids: str,
    include_closed: bool,
    page_limit: int,
):
    client = ClickUpClient(
        ClickUpConfig(
            api_token=api_token,
            team_id=team_id,
            list_ids=split_ids(list_ids),
            assignee_ids=split_ids(assignee_ids),
        )
    )

    return client.get_filtered_team_tasks(
        include_closed=include_closed,
        page_limit=page_limit,
    )


def get_client() -> ClickUpClient:
    return ClickUpClient(
        ClickUpConfig(
            api_token=get_secret("CLICKUP_API_TOKEN"),
            team_id=get_secret("CLICKUP_TEAM_ID"),
            list_ids=split_ids(get_secret("CLICKUP_LIST_IDS")),
            assignee_ids=split_ids(get_secret("CLICKUP_ASSIGNEE_IDS")),
        )
    )


@st.cache_data(ttl=600, show_spinner=False)
def load_folder_reference() -> pd.DataFrame:
    candidates = [
        Path("clickup_folder_ids.csv"),
        Path("data/clickup_folder_ids.csv"),
        Path("assets/clickup_folder_ids.csv"),
    ]

    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return pd.DataFrame(columns=["space_name", "space_id", "folder_name", "folder_id"])

    df = pd.read_csv(path, dtype=str).fillna("")
    required = ["space_name", "space_id", "folder_name", "folder_id"]
    for col in required:
        if col not in df.columns:
            df[col] = ""

    df = df[required].copy()
    for col in required:
        df[col] = df[col].map(clean_text)

    df = df[df["folder_name"].astype(str).str.len() > 0].copy()
    df = df.drop_duplicates(subset=["space_name", "folder_name", "folder_id"])
    return df.sort_values(["space_name", "folder_name"]).reset_index(drop=True)


def get_mapped_space_name(selected_user: str, folder_ref: pd.DataFrame) -> str:
    if selected_user == "All Users":
        return ""

    user_space_map = get_user_space_map()
    mapped = clean_text(user_space_map.get(selected_user, selected_user))

    if folder_ref.empty:
        return mapped

    space_names = set(folder_ref["space_name"].astype(str).map(clean_text).tolist())

    if mapped in space_names:
        return mapped

    if selected_user in space_names:
        return selected_user

    first_name = clean_text(str(selected_user).split(" ")[0])
    if first_name in space_names:
        return first_name

    return mapped


def get_folder_options_for_user(selected_user: str, df: pd.DataFrame, folder_ref: pd.DataFrame) -> pd.DataFrame:
    """Return folder options with folder_name/folder_id/space_name/space_id.

    Prefer the authoritative CSV. Fall back to loaded task data if the CSV does
    not have a matching space for the selected user.
    """
    required = ["space_name", "space_id", "folder_name", "folder_id"]

    if selected_user == "All Users":
        if not folder_ref.empty:
            return folder_ref[required].copy()
        return build_folder_options_from_tasks(df)

    mapped_space_name = get_mapped_space_name(selected_user, folder_ref)

    if not folder_ref.empty and mapped_space_name:
        subset = folder_ref[folder_ref["space_name"].astype(str).map(clean_text).eq(mapped_space_name)].copy()
        if not subset.empty:
            return subset[required].sort_values("folder_name").reset_index(drop=True)

    return build_folder_options_from_tasks(df)


def build_folder_options_from_tasks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["space_name", "space_id", "folder_name", "folder_id"])

    rows = []
    for _, row in df.iterrows():
        folder_name = clean_text(row.get("folder"))
        if not folder_name:
            continue
        rows.append(
            {
                "space_name": clean_text(row.get("space")),
                "space_id": clean_text(row.get("space_id")),
                "folder_name": folder_name,
                "folder_id": clean_text(row.get("folder_id")),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["space_name", "space_id", "folder_name", "folder_id"])

    out = pd.DataFrame(rows).fillna("")
    return out.drop_duplicates(subset=["space_name", "folder_name", "folder_id"]).sort_values("folder_name")


def build_folder_label_map(folder_options: pd.DataFrame, selected_user: str) -> Dict[str, str]:
    """Return label -> folder_id.

    If duplicate folder names exist, include the space in the label.
    """
    if folder_options.empty:
        return {}

    df = folder_options.copy()
    df["folder_name"] = df["folder_name"].map(clean_text)
    df["space_name"] = df["space_name"].map(clean_text)
    df["folder_id"] = df["folder_id"].map(clean_text)

    duplicate_names = set(df[df.duplicated("folder_name", keep=False)]["folder_name"].tolist())

    label_map: Dict[str, str] = {}
    for _, row in df.iterrows():
        name = row["folder_name"]
        folder_id = row["folder_id"]
        space_name = row["space_name"]

        if not name:
            continue

        if selected_user == "All Users" or name in duplicate_names:
            label = f"{space_name} / {name}" if space_name else name
        else:
            label = name

        if folder_id:
            label_map[label] = folder_id
        else:
            label_map[label] = name

    return dict(sorted(label_map.items(), key=lambda item: item[0].lower()))


def attach_folder_reference_to_tasks(df: pd.DataFrame, folder_ref: pd.DataFrame) -> pd.DataFrame:
    """Fill missing folder_id/space_id fields from the CSV where possible."""
    if df.empty:
        return df

    out = df.copy()

    for col in ["space_id", "folder_id"]:
        if col not in out.columns:
            out[col] = ""

    if folder_ref.empty:
        return out

    ref = folder_ref.copy()
    ref["_space_key"] = ref["space_name"].map(clean_text).str.lower()
    ref["_folder_key"] = ref["folder_name"].map(clean_text).str.lower()

    out["_space_key"] = out.get("space", "").map(clean_text).str.lower()
    out["_folder_key"] = out.get("folder", "").map(clean_text).str.lower()

    merged = out.merge(
        ref[["_space_key", "_folder_key", "space_id", "folder_id"]].rename(
            columns={"space_id": "_ref_space_id", "folder_id": "_ref_folder_id"}
        ),
        on=["_space_key", "_folder_key"],
        how="left",
    )

    merged["space_id"] = merged["space_id"].where(merged["space_id"].astype(str).str.len() > 0, merged["_ref_space_id"].fillna(""))
    merged["folder_id"] = merged["folder_id"].where(merged["folder_id"].astype(str).str.len() > 0, merged["_ref_folder_id"].fillna(""))

    return merged.drop(columns=["_space_key", "_folder_key", "_ref_space_id", "_ref_folder_id"], errors="ignore")


def get_list_options_from_tasks(df: pd.DataFrame) -> Dict[str, str]:
    options: Dict[str, str] = {}

    if df.empty:
        return options

    required_cols = {"space", "folder", "list", "list_id"}
    if not required_cols.issubset(set(df.columns)):
        return options

    for _, row in df.iterrows():
        list_id = clean_text(row.get("list_id"))
        if not list_id:
            continue

        space = clean_text(row.get("space"))
        folder = clean_text(row.get("folder"))
        list_name = clean_text(row.get("list"))

        parts = [x for x in [space, folder, list_name] if x]
        label = " / ".join(parts) if parts else list_id
        options[label] = list_id

    return dict(sorted(options.items(), key=lambda item: item[0].lower()))


def apply_main_filters(
    df: pd.DataFrame,
    *,
    selected_folder_ids: List[str],
    selected_folder_names: List[str],
    selected_lists: List[str],
    selected_statuses: List[str],
    selected_priorities: List[str],
    selected_assignees: List[str],
    selected_tags: List[str],
    search: str,
) -> pd.DataFrame:
    filtered = filter_tasks(
        df,
        search=search,
        statuses=selected_statuses,
        priorities=selected_priorities,
        assignees=selected_assignees,
        lists=selected_lists,
        tags=selected_tags,
    )

    if selected_folder_ids and not filtered.empty and "folder_id" in filtered.columns:
        filtered = filtered[filtered["folder_id"].astype(str).isin(selected_folder_ids)]
    elif selected_folder_names and not filtered.empty:
        filtered = filtered[filtered["folder"].astype(str).map(clean_text).isin(selected_folder_names)]

    return filtered


# =========================================================
# Renderers
# =========================================================
def render_header() -> None:
    st.markdown(
        """
        <div class="brand-shell">
            <div class="brand-title">Evolved Commerce<br>ClickUp Command Center</div>
            <div class="brand-subtitle">
                Cleaner task visibility • Client folders • Due date focus • Status updates • Comments • Task creation • AI daily planning
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_info_banner(
        "Folder mapping upgraded",
        "The Client / Folder picker now uses the folder reference CSV first, so account managers show the folders from their actual ClickUp space.",
    )


def render_user_panel(
    *,
    clickup_users: Dict[str, str],
    fallback_assignee_ids: str,
    folder_ref: pd.DataFrame,
):
    st.markdown('<div class="section-title">Workspace View</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">Choose a person. The app maps that person to their ClickUp space and folder IDs when available.</div>',
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)

        user_options = ordered_user_options(clickup_users)

        selected_user = st.selectbox(
            "Person / Space",
            user_options,
            index=0,
            help="Choose whose assigned tasks should be shown.",
        )

        mapped_space_name = get_mapped_space_name(selected_user, folder_ref)

        if selected_user != "All Users":
            if mapped_space_name:
                st.caption(f"Mapped ClickUp space: {mapped_space_name}")
            else:
                st.caption("No specific ClickUp space mapping found.")

        st.markdown("</div>", unsafe_allow_html=True)

    if selected_user == "All Users":
        selected_assignee_ids = ""
    else:
        selected_assignee_ids = clickup_users.get(selected_user, "")

    if not clickup_users:
        selected_user = "Default Assignee Filter" if fallback_assignee_ids else "All Users"
        selected_assignee_ids = fallback_assignee_ids

    return {
        "selected_user": selected_user,
        "selected_assignee_ids": selected_assignee_ids,
        "mapped_space_name": get_mapped_space_name(selected_user, folder_ref),
    }


def render_filter_panel(
    df: pd.DataFrame,
    *,
    selected_user: str,
    folder_ref: pd.DataFrame,
):
    st.markdown('<div class="section-title">Task Filters</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">Client folders come from clickup_folder_ids.csv when available, then fall back to loaded tasks.</div>',
        unsafe_allow_html=True,
    )

    folder_options = get_folder_options_for_user(selected_user, df, folder_ref)
    folder_label_map = build_folder_label_map(folder_options, selected_user)

    with st.container():
        st.markdown('<div class="control-panel">', unsafe_allow_html=True)

        top1, top2 = st.columns([1.2, 1.8])

        with top1:
            selected_folder_labels = st.multiselect(
                "Client / Folder",
                list(folder_label_map.keys()),
                help="Uses folder IDs from clickup_folder_ids.csv where available.",
            )

        with top2:
            search = st.text_input(
                "Search",
                placeholder="task, client, tag, assignee, description...",
            )

        bottom1, bottom2, bottom3, bottom4 = st.columns(4)

        with bottom1:
            list_options = get_unique_values(df, "list")
            selected_lists = st.multiselect(
                "Task List",
                list_options,
                help="Lists are the task workflows inside each client folder.",
            )

        with bottom2:
            status_options = get_unique_values(df, "status")
            selected_statuses = st.multiselect("Status", status_options)

        with bottom3:
            priority_options = ["Urgent", "High", "Normal", "Low", "None"]
            selected_priorities = st.multiselect("Priority", priority_options)

        with bottom4:
            assignee_values = sorted(
                {
                    name.strip()
                    for names in df.get("assignees", pd.Series(dtype=str)).dropna().tolist()
                    for name in str(names).split(",")
                    if name.strip()
                }
            )
            selected_assignees = st.multiselect("Assignee", assignee_values)

        tag_values = sorted(
            {
                tag.strip()
                for tags in df.get("tags", pd.Series(dtype=str)).dropna().tolist()
                for tag in str(tags).split(",")
                if tag.strip()
            }
        )

        with st.expander("More filters", expanded=False):
            selected_tags = st.multiselect("Tags", tag_values)
            card_limit = st.slider(
                "Task cards to show",
                min_value=5,
                max_value=60,
                value=18,
                step=5,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    selected_folder_ids = []
    selected_folder_names = []

    for label in selected_folder_labels:
        value = clean_text(folder_label_map.get(label, ""))
        if value.isdigit():
            selected_folder_ids.append(value)
        else:
            selected_folder_names.append(clean_text(label.split("/")[-1]))

    return {
        "selected_folder_labels": selected_folder_labels,
        "selected_folder_ids": selected_folder_ids,
        "selected_folder_names": selected_folder_names,
        "selected_lists": selected_lists,
        "selected_statuses": selected_statuses,
        "selected_priorities": selected_priorities,
        "selected_assignees": selected_assignees,
        "selected_tags": selected_tags,
        "search": search,
        "card_limit": card_limit,
        "folder_options": folder_options,
    }


def render_summary_metrics(filtered: pd.DataFrame) -> None:
    counts = metric_counts(filtered)

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        render_metric_card("Visible Tasks", str(counts["total"]), tone="brand")
    with c2:
        render_metric_card("Overdue", str(counts["overdue"]), tone="bad" if counts["overdue"] else "good")
    with c3:
        render_metric_card("Due Today", str(counts["today"]), tone="warn" if counts["today"] else "good")
    with c4:
        render_metric_card("Due This Week", str(counts["week"]), tone="brand")
    with c5:
        render_metric_card("No Due Date", str(counts["no_due"]), tone="neutral" if counts["no_due"] else "good")


def render_task_table(df: pd.DataFrame, title: str):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)

    if df.empty:
        st.info("No tasks found here.")
        return

    display_cols = [
        "name",
        "folder",
        "folder_id",
        "list",
        "status",
        "priority",
        "due",
        "assignees",
        "space",
        "space_id",
        "tags",
        "url",
    ]

    available = [c for c in display_cols if c in df.columns]
    shown = df[available].copy()

    shown = shown.rename(
        columns={
            "name": "Task",
            "folder": "Client",
            "folder_id": "Folder ID",
            "list": "Task List",
            "space": "Person Space",
            "space_id": "Space ID",
            "status": "Status",
            "priority": "Priority",
            "due": "Due",
            "assignees": "Assignees",
            "tags": "Tags",
            "url": "ClickUp",
        }
    )

    st.dataframe(
        shown,
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={
            "ClickUp": st.column_config.LinkColumn("ClickUp"),
            "Task": st.column_config.TextColumn("Task", width="large"),
            "Client": st.column_config.TextColumn("Client", width="medium"),
            "Folder ID": st.column_config.TextColumn("Folder ID", width="small"),
            "Task List": st.column_config.TextColumn("Task List", width="medium"),
            "Person Space": st.column_config.TextColumn("Person Space", width="small"),
            "Due": st.column_config.DateColumn("Due"),
        },
    )


def render_task_cards(df: pd.DataFrame, limit: int = 12):
    if df.empty:
        st.info("No matching tasks.")
        return

    for _, row in df.head(limit).iterrows():
        overdue = bool(row.get("is_overdue"))
        due_text = row.get("due") or "No due date"
        status_text = row.get("status") or "None"
        priority_text = row.get("priority") or "None"
        task_url = row.get("url") or ""
        task_name = row.get("name") or "Untitled Task"
        client = row.get("folder") or "No Client / Folder"
        folder_id = row.get("folder_id") or ""
        task_list = row.get("list") or "-"
        assignees = row.get("assignees") or ""
        space = row.get("space") or ""

        badge = "🔴 Overdue" if overdue else "🟢 Open"

        st.markdown('<div class="task-card">', unsafe_allow_html=True)

        if task_url:
            st.markdown(
                f'<div class="task-title"><a href="{task_url}" target="_blank">{task_name}</a></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f'<div class="task-title">{task_name}</div>', unsafe_allow_html=True)

        folder_id_text = f" · <b>Folder ID:</b> {folder_id}" if folder_id else ""

        st.markdown(
            f"""
            <div class="task-meta">
                {badge} · <b>Status:</b> {status_text} · <b>Priority:</b> {priority_text} · <b>Due:</b> {due_text}
            </div>
            <div class="task-meta">
                <b>Client:</b> {client}{folder_id_text} · <b>Task List:</b> {task_list} · <b>Space:</b> {space}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if assignees:
            st.caption(f"Assignees: {assignees}")

        if row.get("description"):
            with st.expander("Description preview"):
                st.write(str(row.get("description"))[:1200])

        st.markdown("</div>", unsafe_allow_html=True)


def render_client_overview(filtered: pd.DataFrame, card_limit: int):
    st.markdown('<div class="section-title">Client Overview</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">Folders are treated as clients. Use this view to spot which accounts need attention.</div>',
        unsafe_allow_html=True,
    )

    if filtered.empty:
        st.info("No tasks found for the current filters.")
        return

    group_cols = ["folder"]
    if "folder_id" in filtered.columns:
        group_cols.append("folder_id")

    client_summary = (
        filtered.groupby(group_cols, dropna=False)
        .agg(
            total_tasks=("id", "count"),
            overdue=("is_overdue", "sum"),
            due_today=("is_due_today", "sum"),
            due_this_week=("is_due_this_week", "sum"),
            no_due_date=("has_no_due_date", "sum"),
        )
        .reset_index()
        .rename(columns={"folder": "Client", "folder_id": "Folder ID"})
        .sort_values(
            ["overdue", "due_today", "due_this_week", "total_tasks"],
            ascending=False,
        )
    )

    client_summary["Client"] = client_summary["Client"].fillna("").map(clean_text).replace("", "No Client / Folder")
    if "Folder ID" not in client_summary.columns:
        client_summary["Folder ID"] = ""

    top_clients = client_summary.head(8).copy()

    card_cols = st.columns(4)
    for idx, row in top_clients.iterrows():
        with card_cols[idx % 4]:
            tone = "#EF4444" if int(row["overdue"]) else "#F97316"
            folder_id_text = f"<div class='client-stat'>Folder ID: {row['Folder ID']}</div>" if row.get("Folder ID") else ""
            st.markdown(
                f"""
                <div class="client-card" style="border-left:5px solid {tone};">
                    <div class="client-name">{row['Client']}</div>
                    {folder_id_text}
                    <div class="client-stat"><b>{int(row['total_tasks'])}</b> visible tasks</div>
                    <div class="client-stat"><b>{int(row['overdue'])}</b> overdue</div>
                    <div class="client-stat"><b>{int(row['due_today'])}</b> due today</div>
                    <div class="client-stat"><b>{int(row['due_this_week'])}</b> due this week</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    inspect_options = [
        f"{row['Client']} ({row['Folder ID']})" if row.get("Folder ID") else row["Client"]
        for _, row in client_summary.iterrows()
    ]

    selected_client_detail = st.selectbox("Inspect client", inspect_options)

    selected_index = inspect_options.index(selected_client_detail)
    selected_row = client_summary.iloc[selected_index]
    selected_folder_id = clean_text(selected_row.get("Folder ID"))
    selected_client_name = clean_text(selected_row.get("Client"))

    if selected_folder_id and "folder_id" in filtered.columns:
        client_detail_df = filtered[filtered["folder_id"].astype(str).eq(selected_folder_id)]
    elif selected_client_name == "No Client / Folder":
        client_detail_df = filtered[filtered["folder"].fillna("").map(clean_text).eq("")]
    else:
        client_detail_df = filtered[filtered["folder"].fillna("").map(clean_text).eq(selected_client_name)]

    render_task_cards(client_detail_df, limit=card_limit)
    render_task_table(client_detail_df, f"{selected_client_name} Tasks")


def render_team_overview(df: pd.DataFrame):
    st.markdown('<div class="section-title">Team Overview</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">A quick workload summary by person/space from the currently loaded ClickUp task data.</div>',
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("No task data loaded.")
        return

    summary = (
        df.groupby("space", dropna=False)
        .agg(
            total_tasks=("id", "count"),
            overdue=("is_overdue", "sum"),
            due_today=("is_due_today", "sum"),
            due_this_week=("is_due_this_week", "sum"),
            no_due_date=("has_no_due_date", "sum"),
        )
        .reset_index()
        .rename(columns={"space": "Person Space"})
        .sort_values(["overdue", "due_today", "due_this_week", "total_tasks"], ascending=False)
    )

    summary["Person Space"] = summary["Person Space"].fillna("").replace("", "No Space")
    display_df(summary, height=420)


def render_folder_ids_admin(folder_ref: pd.DataFrame, folder_options: pd.DataFrame, selected_user: str):
    st.markdown('<div class="section-title">Admin: Folder IDs</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">Use this to verify which folders are tied to each ClickUp space.</div>',
        unsafe_allow_html=True,
    )

    if folder_ref.empty:
        st.warning("No clickup_folder_ids.csv file found in the repo root, data folder, or assets folder.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        render_metric_card("Folder Reference Rows", str(len(folder_ref)), tone="brand")
    with c2:
        render_metric_card("Spaces in CSV", str(folder_ref["space_name"].nunique()), tone="brand")
    with c3:
        render_metric_card("Folders for Current View", str(len(folder_options)), tone="good")

    st.markdown("#### Folders for current person/space")
    display_df(folder_options, height=360)

    st.markdown("#### Full folder reference CSV")
    display_df(folder_ref, height=520)

    st.download_button(
        "Download Folder Reference CSV",
        data=folder_ref.to_csv(index=False).encode("utf-8"),
        file_name="clickup_folder_ids.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_update_tab(df: pd.DataFrame):
    st.markdown('<div class="section-title">Update a ClickUp Task</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">Change status, priority, due date, description, or leave a comment. Nothing writes to ClickUp until you confirm.</div>',
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("Load tasks first.")
        return

    task_options = {
        f"{row['name']} · {row['folder'] or 'No Client'} · {row['status']} · due {row['due'] or 'none'}": row["id"]
        for _, row in df.iterrows()
    }

    selected_label = st.selectbox("Choose task", list(task_options.keys()))
    task_id = task_options[selected_label]
    selected = df[df["id"] == task_id].iloc[0]

    with st.form("task_update_form"):
        selected_url = selected.get("url") or ""
        selected_name = selected.get("name") or "Selected Task"

        if selected_url:
            st.markdown(f"**Selected:** [{selected_name}]({selected_url})")
        else:
            st.markdown(f"**Selected:** {selected_name}")

        u1, u2, u3 = st.columns(3)
        with u1:
            st.write(f"**Client:** {selected.get('folder') or '-'}")
        with u2:
            st.write(f"**Task List:** {selected.get('list') or '-'}")
        with u3:
            st.write(f"**Space:** {selected.get('space') or '-'}")

        new_name = st.text_input("Task name", value=selected.get("name", ""))

        u4, u5, u6 = st.columns(3)
        with u4:
            new_status = st.text_input(
                "Status",
                value=selected.get("status", ""),
                help="Must match a valid status in that ClickUp list.",
            )
        with u5:
            priority_options = ["Do not change", "Urgent", "High", "Normal", "Low"]
            new_priority_label = st.selectbox("Priority", priority_options)
        with u6:
            change_due = st.checkbox("Change due date")
            current_due = selected.get("due")
            new_due = (
                st.date_input("New due date", value=current_due or date.today())
                if change_due
                else None
            )

        change_description = st.checkbox("Replace description")
        new_description = ""

        if change_description:
            new_description = st.text_area(
                "New description",
                value=str(selected.get("description") or ""),
                height=160,
            )

        comment = st.text_area(
            "Add comment",
            placeholder="Optional comment to add to this task",
            height=120,
        )

        notify_all = st.checkbox(
            "Notify all task watchers when adding comment",
            value=False,
        )

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

        st.session_state["pending_update"] = {
            "task_id": task_id,
            "task_name": selected.get("name", ""),
            "changes": changes,
            "comment": comment,
            "notify_all": notify_all,
        }

    pending = st.session_state.get("pending_update")

    if pending:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("### Review before submitting")
        st.write(f"Task: **{pending['task_name']}**")
        st.json(
            {
                "task_changes": pending["changes"],
                "comment": pending["comment"] or None,
            }
        )

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
                    client.add_task_comment(
                        pending["task_id"],
                        pending["comment"],
                        notify_all=bool(pending["notify_all"]),
                    )

                st.success("Task updated in ClickUp.")
                st.session_state.pop("pending_update", None)
                st.cache_data.clear()

            except Exception as exc:
                st.error(f"Update failed: {exc}")


def render_create_task_tab(
    df: pd.DataFrame,
    clickup_users: Dict[str, str],
    selected_user: str,
):
    st.markdown('<div class="section-title">Create a ClickUp Task</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">Create a new task in a ClickUp list. Nothing writes to ClickUp until you confirm.</div>',
        unsafe_allow_html=True,
    )

    list_options = get_list_options_from_tasks(df)
    secret_list_options = get_clickup_create_lists()
    combined_list_options = {**list_options, **secret_list_options}

    if not combined_list_options:
        st.info(
            "No ClickUp lists are available yet. Load tasks first, or add a "
            "[CLICKUP_CREATE_LISTS] section in Streamlit Secrets."
        )
        return

    user_options = ordered_user_options(clickup_users)
    assignable_users = [u for u in user_options if u != "All Users"]

    default_assignees = []
    if selected_user in assignable_users:
        default_assignees = [selected_user]

    with st.form("create_task_form"):
        c1, c2 = st.columns([2, 1])

        with c1:
            create_list_label = st.selectbox(
                "Create task in list",
                list(combined_list_options.keys()),
                help="This is the destination ClickUp list for the new task.",
            )

        with c2:
            priority_label = st.selectbox(
                "Priority",
                ["None", "Urgent", "High", "Normal", "Low"],
            )

        task_name = st.text_input("Task name")

        task_description = st.text_area(
            "Description",
            height=160,
            placeholder="Add useful context, links, instructions, etc.",
        )

        c3, c4, c5 = st.columns(3)

        with c3:
            selected_assignees = st.multiselect(
                "Assign to",
                assignable_users,
                default=default_assignees,
            )

        with c4:
            status = st.text_input(
                "Starting status",
                value="",
                placeholder="Optional. Must match destination list.",
            )

        with c5:
            add_due_date = st.checkbox("Add due date", value=False)
            due_date = st.date_input("Due date", value=date.today()) if add_due_date else None

        preview_create = st.form_submit_button("Preview new task", type="primary")

    if preview_create:
        assignee_ids = []

        for name in selected_assignees:
            user_id = safe_int(clickup_users.get(name))
            if user_id is not None:
                assignee_ids.append(user_id)

        create_payload = {
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

        st.session_state["pending_create"] = create_payload

    pending = st.session_state.get("pending_create")

    if pending:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("### Review before creating")
        st.json(
            {
                "destination": pending["list_label"],
                "name": pending["name"],
                "description": pending["description"] or None,
                "assignees": pending["assignee_names"],
                "status": pending["status"] or None,
                "priority": pending["priority_label"],
                "due_date": pending["due_date"],
            }
        )

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
                created = client.create_task(
                    pending["list_id"],
                    name=pending["name"],
                    description=pending["description"] or None,
                    assignees=pending["assignees"],
                    status=pending["status"] or None,
                    priority=pending["priority"],
                    due_date_ms=pending["due_date_ms"],
                )

                task_url = created.get("url")
                st.success("Task created in ClickUp.")

                if task_url:
                    st.markdown(f"[Open new task in ClickUp]({task_url})")

                st.session_state.pop("pending_create", None)
                st.cache_data.clear()

            except Exception as exc:
                st.error(f"Task creation failed: {exc}")


def render_ai_brief(filtered: pd.DataFrame):
    st.markdown('<div class="section-title">AI Daily Brief</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">Summarizes what to prioritize from the currently filtered task view. This does not change ClickUp.</div>',
        unsafe_allow_html=True,
    )

    if st.button("Generate AI brief", type="primary"):
        brief = get_ai_daily_brief(
            filtered,
            api_key=get_secret("OPENAI_API_KEY"),
            model=get_secret("OPENAI_MODEL", "gpt-5.5-thinking"),
        )
        st.markdown(brief)


# =========================================================
# Sidebar
# =========================================================
with st.sidebar:
    st.markdown("## Tool Guide")
    st.markdown(
        """
**What this tool does**
- Pulls ClickUp tasks by person/space
- Uses your folder ID CSV for client folders
- Shows due, overdue, and priority work
- Lets you update task status, priority, due date, and comments
- Lets you create new ClickUp tasks
- Can generate an AI daily work brief
"""
    )

    st.markdown("---")
    st.markdown("## Data Settings")

    include_closed = st.checkbox("Include closed tasks", value=False)

    page_limit = st.number_input(
        "Max ClickUp pages",
        min_value=1,
        max_value=50,
        value=10,
        step=1,
        help="Each ClickUp page can return up to 100 tasks.",
    )

    refresh_clicked = st.button("Refresh ClickUp Data", use_container_width=True)

    st.markdown("---")
    st.markdown("## App Info")
    st.markdown("**App:** ClickUp Command Center")
    st.markdown("**Owner:** Jake Yorgason, Evolved Commerce")


# =========================================================
# Main app
# =========================================================
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

    user_state = render_user_panel(
        clickup_users=clickup_users,
        fallback_assignee_ids=fallback_assignee_ids,
        folder_ref=folder_ref,
    )

    selected_user = user_state["selected_user"]
    selected_assignee_ids = user_state["selected_assignee_ids"]

    with st.spinner(f"Loading tasks for {selected_user}..."):
        try:
            raw_tasks = load_tasks(
                api_token,
                team_id,
                list_ids,
                selected_assignee_ids,
                include_closed,
                int(page_limit),
            )
            df = normalize_tasks(raw_tasks)
            df = attach_folder_reference_to_tasks(df, folder_ref)
        except Exception as exc:
            st.error(f"Could not load ClickUp tasks for {selected_user}: {exc}")
            st.stop()

    filter_state = render_filter_panel(
        df,
        selected_user=selected_user,
        folder_ref=folder_ref,
    )

    filtered = apply_main_filters(
        df,
        selected_folder_ids=filter_state["selected_folder_ids"],
        selected_folder_names=filter_state["selected_folder_names"],
        selected_lists=filter_state["selected_lists"],
        selected_statuses=filter_state["selected_statuses"],
        selected_priorities=filter_state["selected_priorities"],
        selected_assignees=filter_state["selected_assignees"],
        selected_tags=filter_state["selected_tags"],
        search=filter_state["search"],
    )

    st.caption(
        f"Currently viewing: **{selected_user}**"
        + (
            f" · Client filter: **{', '.join(filter_state['selected_folder_labels'])}**"
            if filter_state["selected_folder_labels"]
            else " · Client filter: **All Clients**"
        )
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    render_summary_metrics(filtered)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    tabs = st.tabs(
        [
            "Focus Queue",
            "Client Board",
            "Today",
            "This Week",
            "Overdue",
            "Team Overview",
            "All Tasks",
            "Update Task",
            "Create Task",
            "AI Brief",
            "Admin: Folder IDs",
        ]
    )

    card_limit = filter_state["card_limit"]

    with tabs[0]:
        st.markdown('<div class="section-title">Focus Queue</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-note">Overdue, due today, urgent, and high-priority tasks from the current view.</div>',
            unsafe_allow_html=True,
        )

        focus = filtered.copy()

        if not focus.empty:
            focus = focus[
                (focus["is_overdue"])
                | (focus["is_due_today"])
                | (focus["priority"].isin(["Urgent", "High"]))
            ]

        render_task_cards(focus, limit=card_limit)

    with tabs[1]:
        render_client_overview(filtered, card_limit)

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
        render_create_task_tab(
            df=df,
            clickup_users=clickup_users,
            selected_user=selected_user,
        )

    with tabs[9]:
        render_ai_brief(filtered)

    with tabs[10]:
        render_folder_ids_admin(
            folder_ref=folder_ref,
            folder_options=filter_state["folder_options"],
            selected_user=selected_user,
        )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    footer_col1, footer_col2, footer_col3 = st.columns([3, 2, 3])
    with footer_col2:
        st.markdown(
            '<div class="footer-note">Evolved Commerce ClickUp Command Center</div>',
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
