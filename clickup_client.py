from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


CLICKUP_BASE_URL = "https://api.clickup.com/api/v2"


class ClickUpError(RuntimeError):
    """Raised when ClickUp returns an error response."""


@dataclass
class ClickUpConfig:
    api_token: str
    team_id: str
    list_ids: Optional[List[str]] = None
    assignee_ids: Optional[List[str]] = None


def _clean_id_list(value: Optional[str | Iterable[str]]) -> List[str]:
    if not value:
        return []

    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]

    return [str(x).strip() for x in value if str(x).strip()]


class ClickUpClient:
    def __init__(self, config: ClickUpConfig):
        if not config.api_token:
            raise ValueError("Missing CLICKUP_API_TOKEN.")

        if not config.team_id:
            raise ValueError("Missing CLICKUP_TEAM_ID.")

        self.config = ClickUpConfig(
            api_token=config.api_token,
            team_id=str(config.team_id),
            list_ids=_clean_id_list(config.list_ids),
            assignee_ids=_clean_id_list(config.assignee_ids),
        )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": self.config.api_token,
                "accept": "application/json",
                "content-type": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[List[Tuple[str, Any]] | Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        url = f"{CLICKUP_BASE_URL}{path}"

        response = self.session.request(
            method,
            url,
            params=params,
            json=json,
            timeout=timeout,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "2"))
            time.sleep(min(retry_after, 10))
            response = self.session.request(
                method,
                url,
                params=params,
                json=json,
                timeout=timeout,
            )

        if not response.ok:
            try:
                detail = response.json()
            except Exception:
                detail = response.text

            raise ClickUpError(f"ClickUp API error {response.status_code}: {detail}")

        if not response.content:
            return {}

        return response.json()

    def get_authorized_teams(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/team").get("teams", [])

    def get_filtered_team_tasks(
        self,
        *,
        include_closed: bool = False,
        subtasks: bool = True,
        page_limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fetch tasks across a Workspace/Team.

        ClickUp returns tasks by page. This method paginates until the API returns
        fewer than 100 tasks or page_limit is reached.
        """
        all_tasks: List[Dict[str, Any]] = []

        for page in range(page_limit):
            params: List[Tuple[str, Any]] = [
                ("page", page),
                ("include_closed", str(include_closed).lower()),
                ("subtasks", str(subtasks).lower()),
                ("order_by", "due_date"),
                ("reverse", "false"),
                ("include_markdown_description", "true"),
            ]

            for list_id in self.config.list_ids or []:
                params.append(("list_ids[]", list_id))

            for assignee_id in self.config.assignee_ids or []:
                params.append(("assignees[]", assignee_id))

            payload = self._request(
                "GET",
                f"/team/{self.config.team_id}/task",
                params=params,
            )

            tasks = payload.get("tasks", [])
            all_tasks.extend(tasks)

            if len(tasks) < 100:
                break

        return all_tasks

    def update_task(
        self,
        task_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int | None] = None,
        due_date_ms: Optional[int | None] = None,
        assignees_add: Optional[List[int]] = None,
        assignees_rem: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}

        if name is not None:
            body["name"] = name

        if description is not None:
            body["description"] = description

        if status is not None:
            body["status"] = status

        if priority is not None:
            body["priority"] = priority

        if due_date_ms is not None:
            body["due_date"] = due_date_ms

        if assignees_add or assignees_rem:
            body["assignees"] = {
                "add": assignees_add or [],
                "rem": assignees_rem or [],
            }

        if not body:
            return {"message": "No changes requested."}

        return self._request("PUT", f"/task/{task_id}", json=body)

    def add_task_comment(
        self,
        task_id: str,
        comment_text: str,
        *,
        notify_all: bool = False,
    ) -> Dict[str, Any]:
        if not comment_text.strip():
            return {"message": "No comment submitted."}

        return self._request(
            "POST",
            f"/task/{task_id}/comment",
            json={
                "comment_text": comment_text.strip(),
                "notify_all": notify_all,
            },
        )

    def create_task(
        self,
        list_id: str,
        *,
        name: str,
        description: Optional[str] = None,
        assignees: Optional[List[int]] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        due_date_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not list_id:
            raise ValueError("A ClickUp list ID is required to create a task.")

        if not name.strip():
            raise ValueError("Task name is required.")

        body: Dict[str, Any] = {
            "name": name.strip(),
        }

        if description:
            body["description"] = description

        if assignees:
            body["assignees"] = assignees

        if status:
            body["status"] = status

        if priority:
            body["priority"] = priority

        if due_date_ms:
            body["due_date"] = due_date_ms

        return self._request("POST", f"/list/{list_id}/task", json=body)


PRIORITY_LABELS = {
    1: "Urgent",
    2: "High",
    3: "Normal",
    4: "Low",
}

PRIORITY_VALUES = {
    "Urgent": 1,
    "High": 2,
    "Normal": 3,
    "Low": 4,
}


def ms_to_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", "0", 0):
        return None

    try:
        return datetime.fromtimestamp(int(value) / 1000)
    except Exception:
        return None


def date_to_clickup_ms(value: Optional[date]) -> Optional[int]:
    if value is None:
        return None

    dt = datetime.combine(value, dt_time(hour=12, minute=0))
    return int(dt.timestamp() * 1000)
