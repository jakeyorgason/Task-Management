# ClickUp Streamlit Dashboard

A cleaner personal ClickUp command center built with Streamlit.

## What it does

- Pulls ClickUp tasks from your Workspace using ClickUp API v2
- Shows clean tabs for:
  - Today
  - This Week
  - Overdue
  - No Due Date
  - All Tasks
  - Update Task
- Filters by status, priority, assignee, list/client, and search text
- Lets you update:
  - Status
  - Priority
  - Due date
  - Task name
  - Task description
  - Comments
- Uses a review/confirmation flow before changing ClickUp
- Optional AI daily brief using OpenAI

## Setup

1. Install requirements:

```bash
pip install -r requirements.txt
```

2. Create secrets:

```bash
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

3. Add your ClickUp token and Workspace/Team ID to `.streamlit/secrets.toml`.

4. Run:

```bash
streamlit run app.py
```

## Getting ClickUp IDs

- Personal API token: ClickUp avatar/settings > Apps > API Token
- Team/Workspace ID: easiest path is using the ClickUp API `GET /team` endpoint, or open ClickUp API docs while authenticated.
- List IDs: open a ClickUp list in your browser; the list ID is usually in the URL.

## Safer update behavior

The app does not auto-update tasks from AI. It shows a preview first, then only writes to ClickUp when you click the confirmation button.

## Notes

ClickUp due dates are stored as Unix timestamps in milliseconds. This app handles conversion to and from normal dates.
