from __future__ import annotations

import os
from datetime import date
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


st.set_page_config(page_title="ClickUp Command Center", page_icon="✅", layout="wide")


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
    """Optional list map for creating tasks.

    Add this in Streamlit Secrets:

    [CLICKUP_CREATE_LISTS]
    "Jake / Incoming Tasks" = "123456789"
    "Anchor Strap Co / Amazon Ads" = "234567890"
    """
    return get_secret_table("CLICKUP_CREATE_LISTS")


def ordered_user_options(clickup_users: Dict[str, str]) -> List[str]:
    if not clickup_users:
        return ["All Users"]

    ordered = [name for name in USER_DISPLAY_ORDER if name in clickup_users]
    extras = sorted([name for name in clickup_users.keys() if name not in ordered])
    user_options = ordered + extras

    if "All Users" not in user_options:
        user_options = ["All Users"] + user_options

    return user_options


def split_ids(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def safe_int(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None

    try:
        return int(str(value).strip())
    except Exception:
        return None


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


def get_unique_values(df: pd.DataFrame, col: str) -> List[str]:
    if df.empty or col not in df.columns:
        return []

    return sorted([x for x in df[col].dropna().unique().tolist() if str(x).strip()])


def get_list_options_from_tasks(df: pd.DataFrame) -> Dict[str, str]:
    """Build a create-task list dropdown from visible tasks.

    This only includes lists that already have at least one task in the loaded data.
    For empty lists, add [CLICKUP_CREATE_LISTS] in Streamlit Secrets.
    """
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

        space = str(row.get("space") or "").strip()
        folder = str(row.get("folder") or "").strip()
        list_name = str(row.get("list") or "").strip()

        parts = [x for x in [space, folder, list_name] if x]
        label = " / ".join(parts) if parts else list_id

        options[label] = list_id

    return dict(sorted(options.items(), key=lambda item: item[0].lower()))


def render_task_table(df: pd.DataFrame, title: str):
    st.subheader(title)

    if df.empty:
        st.info("No tasks found here.")
        return

    display_cols = [
        "name",
        "folder",
        "list",
        "status",
        "priority",
        "due",
        "assignees",
        "space",
        "tags",
        "url",
    ]

    available = [c for c in display_cols if c in df.columns]
    shown = df[available].copy()

    shown = shown.rename(
        columns={
            "name": "Task",
            "folder": "Client",
            "list": "List",
            "space": "Person Space",
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
        column_config={
            "ClickUp": st.column_config.LinkColumn("ClickUp"),
            "Task": st.column_config.TextColumn("Task", width="large"),
            "Client": st.column_config.TextColumn("Client", width="medium"),
            "List": st.column_config.TextColumn("List", width="medium"),
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
        badge = "🔴 Overdue" if overdue else "🟢 Open"

        with st.container(border=True):
            col1, col2 = st.columns([4, 1])

            with col1:
                task_url = row.get("url") or ""
                task_name = row.get("name") or "Untitled Task"

                if task_url:
                    st.markdown(f"### [{task_name}]({task_url})")
                else:
                    st.markdown(f"### {task_name}")

                st.caption(
                    f"{badge} · **Status:** {row.get('status') or 'None'} · "
                    f"**Priority:** {row.get('priority') or 'None'} · "
                    f"**Due:** {due_text}"
                )

                st.write(f"**Client:** {row.get('folder') or '-'}")
                st.write(f"**List:** {row.get('list') or '-'}")

                if row.get("assignees"):
                    st.write(f"**Assignees:** {row.get('assignees')}")

                if row.get("description"):
                    with st.expander("Description preview"):
                        st.write(str(row.get("description"))[:1200])

            with col2:
                if row.get("space"):
                    st.caption(f"Space: {row.get('space')}")

                if row.get("tags"):
                    st.caption(f"Tags: {row.get('tags')}")


def sidebar_filters(df: pd.DataFrame):
    with st.sidebar:
        st.header("Filters")

        search = st.text_input(
            "Search tasks",
            placeholder="client, task, tag, assignee...",
        )

        client_folders = get_unique_values(df, "folder")
        selected_clients = st.multiselect(
            "Client / Folder",
            client_folders,
            help="In your ClickUp setup, folders represent clients.",
        )

        lists = get_unique_values(df, "list")
        selected_lists = st.multiselect(
            "List",
            lists,
            help="Lists are the task lists inside each client folder.",
        )

        statuses = get_unique_values(df, "status")
        selected_statuses = st.multiselect("Status", statuses)

        priorities = ["Urgent", "High", "Normal", "Low", "None"]
        selected_priorities = st.multiselect("Priority", priorities)

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

        selected_tags = st.multiselect("Tags", tag_values)

        st.divider()

        card_limit = st.slider(
            "Task cards to show",
            min_value=5,
            max_value=50,
            value=15,
            step=5,
        )

    filtered = filter_tasks(
        df,
        search=search,
        statuses=selected_statuses,
        priorities=selected_priorities,
        assignees=selected_assignees,
        lists=selected_lists,
        tags=selected_tags,
    )

    if selected_clients and not filtered.empty:
        filtered = filtered[filtered["folder"].isin(selected_clients)]

    return filtered, card_limit, selected_clients


def render_client_overview(filtered: pd.DataFrame, card_limit: int):
    st.subheader("Client Overview")

    if filtered.empty:
        st.info("No tasks found for the current filters.")
        return

    client_summary = (
        filtered.groupby("folder", dropna=False)
        .agg(
            total_tasks=("id", "count"),
            overdue=("is_overdue", "sum"),
            due_today=("is_due_today", "sum"),
            due_this_week=("is_due_this_week", "sum"),
        )
        .reset_index()
        .rename(columns={"folder": "Client"})
        .sort_values(
            ["overdue", "due_today", "due_this_week", "total_tasks"],
            ascending=False,
        )
    )

    client_summary["Client"] = client_summary["Client"].fillna("").replace(
        "",
        "No Client / Folder",
    )

    st.dataframe(
        client_summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Client": st.column_config.TextColumn("Client", width="large"),
            "total_tasks": st.column_config.NumberColumn("Total Tasks"),
            "overdue": st.column_config.NumberColumn("Overdue"),
            "due_today": st.column_config.NumberColumn("Due Today"),
            "due_this_week": st.column_config.NumberColumn("Due This Week"),
        },
    )

    selected_client_detail = st.selectbox(
        "View tasks for client",
        client_summary["Client"].tolist(),
    )

    if selected_client_detail == "No Client / Folder":
        client_detail_df = filtered[filtered["folder"].fillna("").eq("")]
    else:
        client_detail_df = filtered[
            filtered["folder"].fillna("").eq(selected_client_detail)
        ]

    render_task_cards(client_detail_df, limit=card_limit)
    render_task_table(client_detail_df, f"{selected_client_detail} Tasks")


def render_update_tab(df: pd.DataFrame):
    st.subheader("Update a ClickUp Task")
    st.warning("Changes here write directly to ClickUp after you confirm.")

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
            st.write(f"**Selected:** [{selected_name}]({selected_url})")
        else:
            st.write(f"**Selected:** {selected_name}")

        st.write(f"**Client:** {selected.get('folder') or '-'}")
        st.write(f"**List:** {selected.get('list') or '-'}")

        new_name = st.text_input("Task name", value=selected.get("name", ""))

        new_status = st.text_input(
            "Status",
            value=selected.get("status", ""),
            help="Must match a valid status in that ClickUp list.",
        )

        priority_options = ["Do not change", "Urgent", "High", "Normal", "Low"]
        new_priority_label = st.selectbox("Priority", priority_options)

        current_due = selected.get("due")
        change_due = st.checkbox("Change due date")
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

        preview = st.form_submit_button("Preview update")

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
        st.divider()
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
    st.subheader("Create a ClickUp Task")
    st.warning("This creates a new task in ClickUp after you confirm.")

    list_options = get_list_options_from_tasks(df)
    secret_list_options = get_clickup_create_lists()

    combined_list_options = {
        **list_options,
        **secret_list_options,
    }

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
        create_list_label = st.selectbox(
            "Create task in list",
            list(combined_list_options.keys()),
            help="This is the destination ClickUp list for the new task.",
        )

        task_name = st.text_input("Task name")

        task_description = st.text_area(
            "Description",
            height=160,
            placeholder="Add useful context, links, instructions, etc.",
        )

        selected_assignees = st.multiselect(
            "Assign to",
            assignable_users,
            default=default_assignees,
        )

        status = st.text_input(
            "Starting status",
            value="",
            placeholder="Optional. Must match a valid status in the destination list.",
        )

        priority_label = st.selectbox(
            "Priority",
            ["None", "Urgent", "High", "Normal", "Low"],
        )

        add_due_date = st.checkbox("Add due date", value=False)
        due_date = st.date_input("Due date", value=date.today()) if add_due_date else None

        preview_create = st.form_submit_button("Preview new task")

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
        st.divider()
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


def main():
    st.title("✅ ClickUp Command Center")
    st.caption("A cleaner dashboard for tasks, clients, due dates, updates, and quick task creation.")

    api_token = get_secret("CLICKUP_API_TOKEN")
    team_id = get_secret("CLICKUP_TEAM_ID")
    list_ids = get_secret("CLICKUP_LIST_IDS")
    fallback_assignee_ids = get_secret("CLICKUP_ASSIGNEE_IDS")

    clickup_users = get_clickup_users()

    if not api_token or not team_id:
        st.error("Add CLICKUP_API_TOKEN and CLICKUP_TEAM_ID in Streamlit Cloud Secrets.")
        st.stop()

    with st.sidebar:
        st.header("User View")

        user_options = ordered_user_options(clickup_users)

        selected_user = st.selectbox(
            "Choose ClickUp user",
            user_options,
            index=0,
            help="Choose whose assigned tasks should be shown.",
        )

        if selected_user == "All Users":
            assignee_ids = ""
        else:
            assignee_ids = clickup_users.get(selected_user, "")

            if not assignee_ids:
                st.warning(
                    f"No ClickUp user ID found for {selected_user}. "
                    "Check the [CLICKUP_USERS] section in Streamlit Secrets."
                )

        if not clickup_users:
            st.info(
                "No [CLICKUP_USERS] section found in Streamlit Secrets. "
                "Using CLICKUP_ASSIGNEE_IDS instead."
            )
            assignee_ids = fallback_assignee_ids
            selected_user = "Default Assignee Filter" if fallback_assignee_ids else "All Users"

        st.divider()
        st.header("Data")

        include_closed = st.checkbox("Include closed tasks", value=False)

        page_limit = st.number_input(
            "Max ClickUp pages",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            help="Each ClickUp page can return up to 100 tasks.",
        )

        if st.button("Refresh from ClickUp"):
            st.cache_data.clear()
            st.rerun()

    st.info(f"Currently viewing: {selected_user}")

    with st.spinner("Loading ClickUp tasks..."):
        try:
            raw_tasks = load_tasks(
                api_token,
                team_id,
                list_ids,
                assignee_ids,
                include_closed,
                int(page_limit),
            )
            df = normalize_tasks(raw_tasks)

        except Exception as exc:
            st.error(f"Could not load ClickUp tasks: {exc}")
            st.stop()

    filtered, card_limit, selected_clients = sidebar_filters(df)
    counts = metric_counts(filtered)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Visible Tasks", counts["total"])
    c2.metric("Overdue", counts["overdue"])
    c3.metric("Due Today", counts["today"])
    c4.metric("Due This Week", counts["week"])
    c5.metric("No Due Date", counts["no_due"])

    tabs = st.tabs(
        [
            "Focus",
            "Today",
            "This Week",
            "Overdue",
            "No Due Date",
            "Client Overview",
            "All Tasks",
            "AI Brief",
            "Update Task",
            "Create Task",
        ]
    )

    with tabs[0]:
        st.subheader("Focus Queue")

        focus = filtered.copy()

        if not focus.empty:
            focus = focus[
                (focus["is_overdue"])
                | (focus["is_due_today"])
                | (focus["priority"].isin(["Urgent", "High"]))
            ]

        render_task_cards(focus, limit=card_limit)

    with tabs[1]:
        today_df = filtered[filtered["is_due_today"]] if not filtered.empty else filtered
        render_task_cards(today_df, limit=card_limit)
        render_task_table(today_df, "Today Table")

    with tabs[2]:
        week_df = (
            filtered[filtered["is_due_this_week"]]
            if not filtered.empty
            else filtered
        )
        render_task_cards(week_df, limit=card_limit)
        render_task_table(week_df, "This Week Table")

    with tabs[3]:
        overdue_df = (
            filtered[filtered["is_overdue"]]
            if not filtered.empty
            else filtered
        )
        render_task_cards(overdue_df, limit=card_limit)
        render_task_table(overdue_df, "Overdue Table")

    with tabs[4]:
        no_due_df = (
            filtered[filtered["has_no_due_date"]]
            if not filtered.empty
            else filtered
        )
        render_task_cards(no_due_df, limit=card_limit)
        render_task_table(no_due_df, "No Due Date Table")

    with tabs[5]:
        render_client_overview(filtered, card_limit)

    with tabs[6]:
        render_task_table(filtered, "All Visible Tasks")

    with tabs[7]:
        st.subheader("AI Daily Brief")
        st.caption("This only summarizes. It does not change ClickUp.")

        if st.button("Generate AI brief"):
            brief = get_ai_daily_brief(
                filtered,
                api_key=get_secret("OPENAI_API_KEY"),
                model=get_secret("OPENAI_MODEL", "gpt-5.5-thinking"),
            )
            st.markdown(brief)

    with tabs[8]:
        render_update_tab(filtered)

    with tabs[9]:
        render_create_task_tab(
            df=df,
            clickup_users=clickup_users,
            selected_user=selected_user,
        )


if __name__ == "__main__":
    main()
