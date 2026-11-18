#!/usr/bin/env python3
"""Sync the Industrial Defect Image Retrieval (IDIR) plan to Jira Cloud via REST API.

Features:
- Pure Python 3 standard library (no external pip install required).
- Reads credentials safely from a local `.env.jira` file (git-ignored).
- Creates 6 Epics (including Epic 6 ON HOLD for Train Keyboard), 5 historical Sprints
  (2026-09-09 to 2026-11-18), 45 Active Issues (left in `To Do` so all 5 members can
  transition & comment on their own accounts), and 4 On-Hold Issues (Unassigned).
- Attaches official Jira Remote Web Links (with GitHub icon) pointing to verified real
  GitHub commits, Pull Requests, and repository files.
- Idempotent via unique `idir-seed-*` labels and `globalId` remote links.
- Exports a per-member checklist (`outputs/jira_member_checklists.md`) with clickable
  Jira links and ready-to-paste evidence comments for TV1..TV5.

Usage:
    python tools/jira/sync_jira_project.py --check-connection
    python tools/jira/sync_jira_project.py --dry-run
    python tools/jira/sync_jira_project.py
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Ensure sibling module import works regardless of working directory
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from jira_plan_data import (  # noqa: E402
    EPICS,
    GITHUB_ICON_URL,
    GITHUB_REPO_URL,
    ISSUES,
    ROLE_INFO,
    SPRINTS,
)


def configure_console_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def load_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        values[key] = val
    return values


def get_setting(env_values: dict[str, str], key: str, default: str = "") -> str:
    return (os.environ.get(key) or env_values.get(key) or default).strip()


class JiraApiError(RuntimeError):
    def __init__(self, status: int, method: str, path: str, body: str) -> None:
        super().__init__(f"HTTP {status} on {method} {path}: {body}")
        self.status = status
        self.method = method
        self.path = path
        self.body = body


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        parsed = urllib.parse.urlsplit(base_url.strip())
        if parsed.scheme and parsed.netloc:
            self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        else:
            self.base_url = base_url.strip().rstrip("/")
        raw_auth = f"{email}:{api_token}".encode("utf-8")
        token_b64 = base64.b64encode(raw_auth).decode("ascii")
        self.headers = {
            "Authorization": f"Basic {token_b64}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            query = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None},
                doseq=True,
            )
            if query:
                url = f"{url}?{query}"

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise JiraApiError(exc.code, method, path, body) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error calling {url}: {exc}") from exc

    def myself(self) -> dict[str, Any]:
        return self.request("GET", "/rest/api/3/myself")

    def get_project(self, project_key: str) -> dict[str, Any]:
        return self.request("GET", f"/rest/api/3/project/{urllib.parse.quote(project_key)}")

    def list_fields(self) -> list[dict[str, Any]]:
        return self.request("GET", "/rest/api/3/field")

    def get_createmeta_issuetypes(self, project_key: str) -> list[dict[str, Any]]:
        res = self.request(
            "GET",
            f"/rest/api/3/issue/createmeta/{urllib.parse.quote(project_key)}/issuetypes",
        )
        return res.get("issueTypes") or res.get("values") or []

    def get_createmeta_fields(self, project_key: str, issue_type_id: str) -> dict[str, dict[str, Any]]:
        res = self.request(
            "GET",
            f"/rest/api/3/issue/createmeta/{urllib.parse.quote(project_key)}/issuetypes/{issue_type_id}",
            params={"maxResults": 200},
        )
        values = res.get("fields") or res.get("values") or []
        return {item["fieldId"]: item for item in values if "fieldId" in item}

    def list_assignable_users(self, project_key: str) -> list[dict[str, Any]]:
        return self.request(
            "GET",
            "/rest/api/3/user/assignable/search",
            params={"project": project_key, "maxResults": 100},
        )

    def list_boards(self, project_key: str) -> list[dict[str, Any]]:
        res = self.request(
            "GET",
            "/rest/agile/1.0/board",
            params={"projectKeyOrId": project_key, "maxResults": 50},
        )
        return res.get("values") or []

    def list_sprints(self, board_id: int) -> list[dict[str, Any]]:
        sprints: list[dict[str, Any]] = []
        start_at = 0
        while True:
            res = self.request(
                "GET",
                f"/rest/agile/1.0/board/{board_id}/sprint",
                params={"startAt": start_at, "maxResults": 50},
            )
            values = res.get("values") or []
            sprints.extend(values)
            if res.get("isLast", True) or not values:
                break
            start_at += len(values)
        return sprints

    def create_sprint(
        self,
        board_id: int,
        name: str,
        goal: str,
        start_date: str | None,
        end_date: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "originBoardId": board_id,
            "goal": goal,
        }
        if start_date:
            payload["startDate"] = start_date
        if end_date:
            payload["endDate"] = end_date
        try:
            return self.request("POST", "/rest/agile/1.0/sprint", payload=payload)
        except JiraApiError as exc:
            # Some board configurations reject dates until Sprint is started; retry without dates.
            if exc.status == 400 and (start_date or end_date):
                fallback = {"name": name, "originBoardId": board_id, "goal": goal}
                created = self.request("POST", "/rest/agile/1.0/sprint", payload=fallback)
                print(
                    f"  [WARN] Jira không cho đặt sẵn ngày khi tạo Sprint future '{name}'. "
                    "Bạn có thể nhập đúng ngày này lúc bấm Start Sprint."
                )
                return created
            raise

    def move_issues_to_sprint(self, sprint_id: int, issue_keys: list[str]) -> None:
        if not issue_keys:
            return
        # Agile API allows up to 50 issues per request
        for idx in range(0, len(issue_keys), 50):
            batch = issue_keys[idx : idx + 50]
            self.request(
                "POST",
                f"/rest/agile/1.0/sprint/{sprint_id}/issue",
                payload={"issues": batch},
            )

    def search_seeded_issues(self, project_key: str) -> dict[str, dict[str, Any]]:
        """Return map of seed_id (`idir-seed-*`) -> existing issue dict."""
        jql = f'project = "{project_key}" AND labels is not EMPTY ORDER BY created ASC'
        issues: list[dict[str, Any]] = []
        try:
            next_page_token: str | None = None
            while True:
                payload: dict[str, Any] = {
                    "jql": jql,
                    "maxResults": 100,
                    "fields": ["summary", "labels", "issuetype", "status", "assignee"],
                }
                if next_page_token:
                    payload["nextPageToken"] = next_page_token
                res = self.request("POST", "/rest/api/3/search/jql", payload=payload)
                issues.extend(res.get("issues") or [])
                if res.get("isLast", True) or not res.get("nextPageToken"):
                    break
                next_page_token = res["nextPageToken"]
        except JiraApiError as exc:
            if exc.status not in (404, 405, 410):
                raise
            # Fallback for older Jira instances
            res = self.request(
                "POST",
                "/rest/api/3/search",
                payload={
                    "jql": jql,
                    "maxResults": 200,
                    "fields": ["summary", "labels", "issuetype", "status", "assignee"],
                },
            )
            issues = res.get("issues") or []

        seed_map: dict[str, dict[str, Any]] = {}
        for issue in issues:
            labels = issue.get("fields", {}).get("labels") or []
            for lbl in labels:
                if isinstance(lbl, str) and lbl.startswith("idir-seed-"):
                    seed_map[lbl] = issue
        return seed_map

    def create_issue(self, fields: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/rest/api/3/issue", payload={"fields": fields})

    def update_issue(self, issue_key: str, fields: dict[str, Any]) -> None:
        self.request("PUT", f"/rest/api/3/issue/{issue_key}", payload={"fields": fields})

    def add_remote_link(self, issue_key: str, global_id: str, title: str, url: str) -> None:
        payload = {
            "globalId": global_id,
            "application": {
                "type": "com.github",
                "name": "GitHub",
            },
            "relationship": "implemented in",
            "object": {
                "url": url,
                "title": title,
                "icon": {
                    "url16x16": GITHUB_ICON_URL,
                    "title": "GitHub",
                },
            },
        }
        self.request("POST", f"/rest/api/3/issue/{issue_key}/remotelink", payload=payload)

    def try_transition(self, issue_key: str, target_names: tuple[str, ...]) -> str | None:
        res = self.request("GET", f"/rest/api/3/issue/{issue_key}/transitions")
        transitions = res.get("transitions") or []
        wanted = {n.lower() for n in target_names}
        for tr in transitions:
            tr_name = (tr.get("name") or "").strip().lower()
            to_name = (tr.get("to", {}).get("name") or "").strip().lower()
            if tr_name in wanted or to_name in wanted:
                self.request(
                    "POST",
                    f"/rest/api/3/issue/{issue_key}/transitions",
                    payload={"transition": {"id": tr["id"]}},
                )
                return tr.get("to", {}).get("name") or tr.get("name")
        return None

    def list_comments(self, issue_key: str) -> list[dict[str, Any]]:
        res = self.request("GET", f"/rest/api/3/issue/{issue_key}/comment", params={"maxResults": 50})
        return res.get("comments") or []

    def add_comment(self, issue_key: str, body_adf: dict[str, Any]) -> None:
        self.request(
            "POST",
            f"/rest/api/3/issue/{issue_key}/comment",
            payload={"body": body_adf},
        )


def adf_paragraph(text: str, bold_prefix: str | None = None) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if bold_prefix:
        content.append({"type": "text", "text": bold_prefix, "marks": [{"type": "strong"}]})
    if text:
        content.append({"type": "text", "text": text})
    return {"type": "paragraph", "content": content}


def adf_heading(text: str, level: int = 3) -> dict[str, Any]:
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": [{"type": "text", "text": text}],
    }


def adf_bullet_list(items: list[str], code: bool = False) -> dict[str, Any]:
    list_items = []
    for item in items:
        text_node: dict[str, Any] = {"type": "text", "text": item}
        if code:
            text_node["marks"] = [{"type": "code"}]
        list_items.append(
            {
                "type": "listItem",
                "content": [{"type": "paragraph", "content": [text_node]}],
            }
        )
    return {"type": "bulletList", "content": list_items}


def build_epic_adf(epic: dict[str, Any]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = [
        adf_heading("Mục tiêu Epic", 3),
        adf_paragraph(epic["objective"]),
    ]
    if epic.get("on_hold"):
        blocks.append(
            adf_paragraph(
                "Tạm ngưng phân công (Unassigned) và không đưa vào Sprint 1–5 để tập trung nghiệm thu module Phone Defect.",
                bold_prefix="Trạng thái phạm vi (CR-01): ",
            )
        )
    elif epic.get("start_date") and epic.get("due_date"):
        blocks.append(
            adf_paragraph(
                f"{epic['start_date']} → {epic['due_date']}",
                bold_prefix="Mốc thời gian kế hoạch: ",
            )
        )
    return {"type": "doc", "version": 1, "content": blocks}


def build_issue_adf(issue: dict[str, Any], sprint_name: str | None) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = [
        adf_heading("Mục tiêu công việc", 3),
        adf_paragraph(issue["objective"]),
    ]
    role = issue.get("role")
    if role:
        blocks.append(adf_paragraph(f"{role} — {ROLE_INFO[role]}", bold_prefix="Phụ trách phần việc: "))
    else:
        blocks.append(adf_paragraph("Unassigned — Tạm ngưng phân công theo Change Request CR-01", bold_prefix="Phụ trách: "))

    if sprint_name and issue.get("start_date") and issue.get("due_date"):
        blocks.append(
            adf_paragraph(
                f"{sprint_name} | {issue['start_date']} → {issue['due_date']} | {issue['story_points']} SP",
                bold_prefix="Lịch trình kế hoạch: ",
            )
        )

    if issue.get("files"):
        blocks.append(adf_heading("Mã nguồn & Tài liệu liên quan", 3))
        blocks.append(adf_bullet_list(issue["files"], code=True))

    if issue.get("acceptance_criteria"):
        blocks.append(adf_heading("Tiêu chí hoàn thành (Acceptance Criteria)", 3))
        blocks.append(adf_bullet_list(issue["acceptance_criteria"], code=False))

    return {"type": "doc", "version": 1, "content": blocks}


def resolve_issue_type_map(raw_types: list[dict[str, Any]]) -> dict[str, str]:
    by_lower = {t["name"].strip().lower(): t["id"] for t in raw_types if "name" in t and "id" in t}
    task_id = by_lower.get("task") or next(iter(by_lower.values()), "")
    if not task_id:
        raise RuntimeError("Không tìm thấy Issue Type nào trong Jira Project.")
    return {
        "Epic": by_lower.get("epic", ""),
        "Story": by_lower.get("story") or task_id,
        "Task": task_id,
        "Bug": by_lower.get("bug") or task_id,
    }


def detect_custom_fields(
    all_fields: list[dict[str, Any]],
    sample_create_fields: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None, str | None]:
    """Detect (story_points_field_id, start_date_field_id, epic_name_field_id)."""
    story_candidates: list[str] = []
    start_candidates: list[str] = []
    epic_name_id: str | None = None

    for f in all_fields:
        fid = f.get("id", "")
        name = (f.get("name") or "").strip().lower()
        if name in ("story point estimate", "story points"):
            story_candidates.append(fid)
        elif name == "start date":
            start_candidates.append(fid)
        elif name == "epic name":
            epic_name_id = fid

    story_id = next((c for c in story_candidates if c in sample_create_fields), None)
    if not story_id and story_candidates:
        story_id = story_candidates[0]

    start_id = next((c for c in start_candidates if c in sample_create_fields), None)
    if not start_id and start_candidates:
        start_id = start_candidates[0]

    return story_id, start_id, epic_name_id


def resolve_role_accounts(
    env_values: dict[str, str],
    assignable_users: list[dict[str, Any]],
) -> dict[str, dict[str, str] | None]:
    resolved: dict[str, dict[str, str] | None] = {}
    for role in ("TV1", "TV2", "TV3", "TV4", "TV5"):
        raw = get_setting(env_values, f"{role}_USER") or get_setting(env_values, f"{role}_EMAIL")
        if not raw:
            resolved[role] = None
            continue
        raw_lower = raw.lower()
        matched = None
        for u in assignable_users:
            acc_id = (u.get("accountId") or "").strip()
            email = (u.get("emailAddress") or "").strip().lower()
            display = (u.get("displayName") or "").strip().lower()
            if raw == acc_id or (email and raw_lower == email) or (display and raw_lower == display):
                matched = {
                    "accountId": acc_id,
                    "displayName": u.get("displayName") or raw,
                    "email": u.get("emailAddress") or "",
                }
                break
        if matched is None:
            print(
                f"  [WARN] Không tìm thấy user '{raw}' cho {role} trong danh sách thành viên project. "
                "Kiểm tra lại lời mời email hoặc dùng accountId từ lệnh --check-connection."
            )
        resolved[role] = matched
    return resolved


def write_member_checklist(
    out_path: Path,
    site_url: str,
    project_key: str,
    key_map: dict[str, str],
    role_users: dict[str, dict[str, str] | None],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sprint_lookup = {s["code"]: s for s in SPRINTS}

    lines: list[str] = [
        f"# Checklist Thao Tác Jira Cho 5 Thành Viên — Project `{project_key}`",
        "",
        "Tất cả 45 task Active đã được tạo ở trạng thái **`To Do`** và gắn sẵn **Web Links GitHub**.",
        "Mỗi thành viên đăng nhập **tài khoản Jira của chính mình**, chạy lần lượt từng Sprint theo sự điều phối của PM (`TV5`):",
        "",
        "1. Khi PM bấm **Start Sprint**, mở danh sách thẻ bên dưới của bạn.",
        "2. Kéo từng thẻ qua `In Progress` → `In Review` → `Done`.",
        "3. Dán phần bình luận gợi ý (kèm bằng chứng thật) vào thẻ rồi báo PM đóng Sprint.",
        "",
        "---",
        "",
    ]

    for role in ("TV1", "TV2", "TV3", "TV4", "TV5"):
        user_info = role_users.get(role)
        who = f"{user_info['displayName']}" if user_info else "(chưa gán tài khoản Jira)"
        role_issues = [i for i in ISSUES if i["role"] == role]
        total_sp = sum(i["story_points"] for i in role_issues)
        lines.append(f"## {role} — {who}")
        lines.append(f"**Vai trò:** {ROLE_INFO[role]} | **Tổng:** {len(role_issues)} issues ({total_sp} SP)")
        lines.append("")
        lines.append("| Sprint | Jira Key | Tiêu đề | Hạn chót | SP | Bình luận gợi ý khi kéo sang Done |")
        lines.append("| :---: | :---: | :--- | :---: | :---: | :--- |")
        for issue in role_issues:
            jira_key = key_map.get(issue["code"], f"{project_key}-{issue['code']}")
            link_md = f"[{jira_key}]({site_url}/browse/{jira_key})" if site_url else f"`{jira_key}`"
            sp_info = sprint_lookup[issue["sprint"]]
            first_link = issue["github_links"][0][1] if issue["github_links"] else GITHUB_REPO_URL
            comment = f"Đã hoàn thành đúng tiêu chí; mã nguồn & bằng chứng đã gắn tại Web Links ({first_link})."
            lines.append(
                f"| {sp_info['code']} | {link_md} | {issue['summary']} | {issue['due_date']} | {issue['story_points']} | {comment} |"
            )
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## Hạng mục Tạm Ngưng Phân Công (`Epic 6 — ON HOLD`)",
            "Các thẻ `T46`–`T49` (Train Keyboard) được giữ `Unassigned` và nằm ngoài Sprint 1–5 theo **Change Request CR-01**.",
            "",
        ]
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def run_check_connection(client: JiraClient, project_key: str, env_values: dict[str, str]) -> int:
    print("== 1. Kiểm tra xác thực Jira Cloud ==")
    me = client.myself()
    print(f"  OK — Đang đăng nhập với: {me.get('displayName')} ({me.get('emailAddress')})")

    print(f"\n== 2. Kiểm tra Project '{project_key}' ==")
    proj = client.get_project(project_key)
    print(f"  OK — {proj.get('name')} (key={proj.get('key')}, style={proj.get('style')})")

    print("\n== 3. Kiểm tra Issue Types & Custom Fields ==")
    raw_types = client.get_createmeta_issuetypes(project_key)
    type_map = resolve_issue_type_map(raw_types)
    print(f"  Issue Types: {[t['name'] for t in raw_types]}")
    sample_fields = client.get_createmeta_fields(project_key, type_map["Task"])
    story_id, start_id, epic_name_id = detect_custom_fields(client.list_fields(), sample_fields)
    print(f"  Story Points field: {story_id or '(không có trên screen)'}")
    print(f"  Start Date field:   {start_id or '(không có trên screen)'}")
    print(f"  Epic Name field:    {epic_name_id or '(không cần)'}")

    print("\n== 4. Kiểm tra Scrum Board ==")
    boards = client.list_boards(project_key)
    if boards:
        for b in boards:
            print(f"  Board id={b['id']} | name={b['name']} | type={b['type']}")
    else:
        print("  [WARN] Chưa tìm thấy Scrum Board nào cho project này. Hãy tạo project theo template Scrum!")

    print("\n== 5. Danh sách Thành viên có thể gán việc (Copy accountId hoặc email vào .env.jira) ==")
    users = client.list_assignable_users(project_key)
    for u in users:
        if u.get("accountType") == "atlassian":
            print(
                f"  - {u.get('displayName', ''):<28} | email={u.get('emailAddress', '(ẩn)'):<32} | accountId={u.get('accountId')}"
            )

    print("\n== 6. Kiểm tra ánh xạ TV1..TV5 từ .env.jira ==")
    role_users = resolve_role_accounts(env_values, users)
    for role, info in role_users.items():
        status = f"OK -> {info['displayName']} ({info['accountId']})" if info else "CHƯA GÁN / CHƯA KHỚP"
        print(f"  {role}: {status}")
    return 0


def filter_target_issues(
    only_role: str | None,
    sprint_code: str | None,
) -> list[dict[str, Any]]:
    selected = list(ISSUES)
    if only_role:
        selected = [i for i in selected if i.get("role") == only_role]
    if sprint_code:
        selected = [i for i in selected if i.get("sprint") == sprint_code]
    return selected


def build_evidence_comment_adf(issue: dict[str, Any]) -> dict[str, Any]:
    links_text = [f"{title}: {url}" for title, url in issue.get("github_links") or []]
    blocks: list[dict[str, Any]] = [
        adf_paragraph(
            f"Đã hoàn thành đầu việc {issue['code']} theo đúng tiêu chí nghiệm thu ({issue['start_date']} → {issue['due_date']}).",
            bold_prefix="[Cập nhật hoàn thành] ",
        )
    ]
    if issue.get("files"):
        blocks.append(adf_paragraph("Tệp mã nguồn / tài liệu bàn giao:", bold_prefix=""))
        blocks.append(adf_bullet_list(issue["files"], code=True))
    if links_text:
        blocks.append(adf_paragraph("Bằng chứng GitHub đã gắn trên Web Links:", bold_prefix=""))
        blocks.append(adf_bullet_list(links_text, code=False))
    return {"type": "doc", "version": 1, "content": blocks}


def run_dry_run(
    site_url: str,
    project_key: str,
    checklist_out: Path,
    only_role: str | None = None,
    sprint_code: str | None = None,
    complete_my_tasks: bool = False,
) -> int:
    target_issues = filter_target_issues(only_role, sprint_code)
    active = [i for i in target_issues if not i.get("on_hold")]
    paused = [i for i in target_issues if i.get("on_hold")]

    mode_label = "COMPLETE MY TASKS (DRY-RUN)" if complete_my_tasks else "SYNC PLAN (DRY-RUN)"
    print(f"== {mode_label} ==")
    print(f"Repository GitHub: {GITHUB_REPO_URL}")
    if only_role:
        print(f"Lọc vai trò (KHÔNG đụng phần người khác): {only_role} — {ROLE_INFO[only_role]}")
    if sprint_code:
        print(f"Lọc Sprint: {sprint_code}")

    if not complete_my_tasks:
        needed_epics = {i["epic"] for i in target_issues} if only_role else {e["code"] for e in EPICS}
        needed_sprints = {i["sprint"] for i in active if i["sprint"]} if (only_role or sprint_code) else {s["code"] for s in SPRINTS}
        print(f"Epics liên quan:   {len(needed_epics)} ({', '.join(sorted(needed_epics))})")
        print(f"Sprints liên quan: {len(needed_sprints)} ({', '.join(sorted(needed_sprints))})")

    total_links = sum(len(i["github_links"]) for i in target_issues)
    if not only_role and not sprint_code and not complete_my_tasks:
        total_links += sum(len(e["github_links"]) for e in EPICS)
    print(f"Issues trong phạm vi: {len(active)} Active + {len(paused)} On Hold ({sum(i['story_points'] for i in active)} SP)")
    print(f"GitHub Remote Web Links trong phạm vi: {total_links}")

    if only_role or sprint_code or complete_my_tasks:
        print("\nDanh sách chi tiết sẽ xử lý:")
        for issue in target_issues:
            print(
                f"  - [{issue['sprint'] or 'ON-HOLD'}] {issue['code']} ({issue['role'] or 'Unassigned'} | "
                f"{issue['story_points']} SP | {issue['start_date']}..{issue['due_date']}): {issue['summary']}"
            )
    else:
        print("\nPhân bổ theo 5 phần (TV1..TV5):")
        for role in ("TV1", "TV2", "TV3", "TV4", "TV5"):
            r_issues = [i for i in active if i["role"] == role]
            print(f"  {role}: {len(r_issues):2d} issues | {sum(i['story_points'] for i in r_issues):2d} SP | {ROLE_INFO[role]}")

        key_map = {i["code"]: f"{project_key}-{idx}" for idx, i in enumerate(ISSUES, start=1)}
        write_member_checklist(checklist_out, site_url, project_key, key_map, {})
        print(f"\nĐã xuất thử Checklist 5 thành viên tại: {checklist_out}")

    print("Không có dữ liệu nào bị thay đổi trên Jira (chế độ --dry-run).")
    return 0


def run_complete_my_tasks(
    client: JiraClient,
    project_key: str,
    only_role: str | None,
    sprint_code: str | None,
) -> int:
    if not only_role:
        raise RuntimeError(
            "Chế độ --complete-my-tasks bắt buộc phải truyền --only-role (TV1|TV2|TV3|TV4|TV5) "
            "để đảm bảo chỉ thao tác phần việc của riêng bạn."
        )

    me = client.myself()
    my_account_id = (me.get("accountId") or "").strip()
    print(f"Đang chạy dưới tài khoản Jira của bạn: {me.get('displayName')} ({my_account_id})")
    print(f"Phạm vi lọc: chỉ vai trò {only_role}" + (f", chỉ Sprint {sprint_code}" if sprint_code else ", toàn bộ Sprints của bạn"))

    existing_by_seed = client.search_seeded_issues(project_key)
    target_issues = filter_target_issues(only_role, sprint_code)
    updated_count = 0
    skipped_other_owner = 0

    for issue in target_issues:
        seed_id = issue["seed_id"]
        existing = existing_by_seed.get(seed_id)
        if not existing:
            print(f"  [SKIP] {issue['code']} chưa có trên Jira (hãy chạy sync trước).")
            continue

        issue_key = existing["key"]
        assignee = (existing.get("fields", {}).get("assignee") or {})
        assignee_id = (assignee.get("accountId") or "").strip()
        if assignee_id != my_account_id:
            skipped_other_owner += 1
            who = assignee.get("displayName") or "Unassigned"
            print(
                f"  [GUARD-SKIP] {issue_key} ({issue['code']}) đang gán cho '{who}', "
                "KHÔNG khớp tài khoản đang đăng nhập -> bỏ qua để không đụng thẻ người khác."
            )
            continue

        current_status = (existing.get("fields", {}).get("status", {}).get("name") or "").strip()
        if current_status.lower() == "done":
            print(f"  [OK] {issue_key} ({issue['code']}) đã ở trạng thái Done.")
        else:
            steps_done: list[str] = []
            for step_targets in (
                ("In Progress", "Đang làm", "Doing"),
                ("In Review", "Review", "Code Review"),
                ("Done", "Hoàn thành", "Completed"),
            ):
                moved = client.try_transition(issue_key, step_targets)
                if moved:
                    steps_done.append(moved)
            print(f"  [DONE] {issue_key} ({issue['code']}): {current_status} -> {' -> '.join(steps_done) or '(không đổi)'}")

        # Add evidence comment once (idempotent)
        existing_comments = client.list_comments(issue_key)
        already_commented = any("[Cập nhật hoàn thành]" in json.dumps(c.get("body", {}), ensure_ascii=False) for c in existing_comments)
        if not already_commented:
            client.add_comment(issue_key, build_evidence_comment_adf(issue))
            print(f"         -> Đã đăng bình luận xác nhận & bằng chứng GitHub trên {issue_key}")
        updated_count += 1

    print(f"\nHoàn tất phần việc của {only_role}: đã xử lý {updated_count} thẻ (bỏ qua an toàn {skipped_other_owner} thẻ không thuộc tài khoản của bạn).")
    return 0


def run_live_sync(
    client: JiraClient,
    site_url: str,
    project_key: str,
    env_values: dict[str, str],
    checklist_out: Path,
    only_role: str | None = None,
    sprint_code: str | None = None,
) -> int:
    me = client.myself()
    print(f"Đã kết nối Jira dưới tài khoản: {me.get('displayName')} ({me.get('emailAddress')})")
    proj = client.get_project(project_key)
    print(f"Project đích: {proj.get('name')} ({project_key}, style={proj.get('style')})")

    target_issues = filter_target_issues(only_role, sprint_code)
    if only_role:
        print(f"Chế độ lọc vai trò: CHỈ đồng bộ {len(target_issues)} thẻ của {only_role} (không tạo/chạm thẻ thành viên khác).")
    if sprint_code:
        print(f"Chế độ lọc Sprint: CHỈ đồng bộ Sprint {sprint_code}.")

    target_epic_codes = {i["epic"] for i in target_issues} if (only_role or sprint_code) else {e["code"] for e in EPICS}
    target_sprint_codes = {i["sprint"] for i in target_issues if i.get("sprint")} if (only_role or sprint_code) else {s["code"] for s in SPRINTS}
    target_epics = [e for e in EPICS if e["code"] in target_epic_codes]
    target_sprints = [s for s in SPRINTS if s["code"] in target_sprint_codes]

    raw_types = client.get_createmeta_issuetypes(project_key)
    type_map = resolve_issue_type_map(raw_types)
    if not type_map["Epic"]:
        raise RuntimeError("Project Jira không có Issue Type 'Epic'. Hãy bật Epic trước khi chạy.")

    create_fields_by_type: dict[str, dict[str, dict[str, Any]]] = {}
    for t_name, t_id in type_map.items():
        create_fields_by_type[t_name] = client.get_createmeta_fields(project_key, t_id)

    all_fields = client.list_fields()
    story_field_id, start_field_id, epic_name_field_id = detect_custom_fields(
        all_fields, create_fields_by_type["Task"]
    )
    print(f"Custom fields phát hiện: StoryPoints={story_field_id}, StartDate={start_field_id}")

    # Resolve Board ID
    board_override = get_setting(env_values, "JIRA_BOARD_ID")
    if board_override:
        board_id = int(board_override)
    else:
        boards = client.list_boards(project_key)
        scrum_boards = [b for b in boards if (b.get("type") or "").lower() == "scrum"]
        chosen = scrum_boards[0] if scrum_boards else (boards[0] if boards else None)
        if not chosen:
            raise RuntimeError(f"Không tìm thấy Scrum Board nào cho project {project_key}.")
        board_id = int(chosen["id"])
        print(f"Scrum Board: id={board_id} ({chosen['name']})")

    # Resolve 5 team members
    users = client.list_assignable_users(project_key)
    role_users = resolve_role_accounts(env_values, users)
    if only_role and not role_users.get(only_role):
        role_users[only_role] = {
            "accountId": (me.get("accountId") or "").strip(),
            "displayName": me.get("displayName") or me.get("emailAddress") or only_role,
            "email": me.get("emailAddress") or "",
        }
        print(f"Tự động gán {only_role} vào tài khoản đang đăng nhập: {role_users[only_role]['displayName']}")

    # Fetch existing seeded issues for idempotency
    existing_by_seed = client.search_seeded_issues(project_key)
    print(f"Đã tìm thấy {len(existing_by_seed)} issue đã đồng bộ trước đó (sẽ không tạo trùng).")

    # 1. Create / reuse Epics in scope
    print(f"\n== Bước 1/4: Đồng bộ {len(target_epics)} Epics & gắn GitHub Web Links ==")
    epic_key_by_code: dict[str, str] = {}
    epic_allowed = create_fields_by_type["Epic"]
    for epic in target_epics:
        seed_id = epic["seed_id"]
        if seed_id in existing_by_seed:
            epic_key = existing_by_seed[seed_id]["key"]
            print(f"  [SKIP] Epic {epic['code']} đã tồn tại -> {epic_key}")
        else:
            fields: dict[str, Any] = {
                "project": {"key": project_key},
                "issuetype": {"id": type_map["Epic"]},
                "summary": epic["summary"],
                "description": build_epic_adf(epic),
                "labels": list(dict.fromkeys([seed_id, *epic["labels"]])),
            }
            if epic_name_field_id and epic_name_field_id in epic_allowed:
                fields[epic_name_field_id] = epic["summary"]
            if start_field_id and epic.get("start_date") and start_field_id in epic_allowed:
                fields[start_field_id] = epic["start_date"]
            if epic.get("due_date") and "duedate" in epic_allowed:
                fields["duedate"] = epic["due_date"]

            created = client.create_issue(fields)
            epic_key = created["key"]
            print(f"  [CREATE] Epic {epic['code']} -> {epic_key}: {epic['summary']}")

            if epic.get("on_hold"):
                tr = client.try_transition(epic_key, ("On Hold", "Paused", "Tạm ngưng"))
                if tr:
                    print(f"           -> Đã chuyển trạng thái sang '{tr}'")

        epic_key_by_code[epic["code"]] = epic_key
        for idx, (title, url) in enumerate(epic["github_links"], start=1):
            client.add_remote_link(epic_key, f"{seed_id}-link-{idx}", title, url)

    # 2. Create / reuse Sprints in scope
    print(f"\n== Bước 2/4: Đồng bộ {len(target_sprints)} Sprints (09/09/2026 -> 18/11/2026) ==")
    existing_sprints = {s["name"]: s for s in client.list_sprints(board_id)}
    sprint_id_by_code: dict[str, int] = {}
    for sp in target_sprints:
        if sp["name"] in existing_sprints:
            sp_id = int(existing_sprints[sp["name"]]["id"])
            print(f"  [SKIP] {sp['code']} đã tồn tại -> sprintId={sp_id} ({sp['name']})")
        else:
            created_sp = client.create_sprint(
                board_id=board_id,
                name=sp["name"],
                goal=sp["goal"],
                start_date=sp["start_date"],
                end_date=sp["end_date"],
            )
            sp_id = int(created_sp["id"])
            print(f"  [CREATE] {sp['code']} -> sprintId={sp_id} ({sp['name']})")
        sprint_id_by_code[sp["code"]] = sp_id

    # 3. Create / reuse Issues in scope + attach GitHub Web Links
    print(f"\n== Bước 3/4: Đồng bộ {len(target_issues)} Issues & gắn GitHub Web Links ==")
    sprint_name_by_code = {s["code"]: s["name"] for s in SPRINTS}
    issue_key_by_code: dict[str, str] = {}
    issues_per_sprint: dict[str, list[str]] = {s["code"]: [] for s in target_sprints}

    for issue in target_issues:
        seed_id = issue["seed_id"]
        sp_code = issue["sprint"]
        sp_name = sprint_name_by_code.get(sp_code) if sp_code else None
        i_type = issue["issue_type"]
        allowed = create_fields_by_type[i_type]

        if seed_id in existing_by_seed:
            issue_key = existing_by_seed[seed_id]["key"]
            print(f"  [SKIP] {issue['code']} đã tồn tại -> {issue_key}")
        else:
            fields = {
                "project": {"key": project_key},
                "issuetype": {"id": type_map[i_type]},
                "summary": issue["summary"],
                "description": build_issue_adf(issue, sp_name),
                "labels": list(dict.fromkeys([seed_id, *issue["labels"]])),
            }
            epic_key = epic_key_by_code.get(issue["epic"])
            if epic_key and "parent" in allowed:
                fields["parent"] = {"key": epic_key}
            if "priority" in allowed:
                fields["priority"] = {"name": issue["priority"]}
            if issue.get("due_date") and "duedate" in allowed:
                fields["duedate"] = issue["due_date"]
            if start_field_id and issue.get("start_date") and start_field_id in allowed:
                fields[start_field_id] = issue["start_date"]
            if story_field_id and issue.get("story_points") is not None and story_field_id in allowed:
                fields[story_field_id] = issue["story_points"]

            role = issue.get("role")
            if role and role_users.get(role) and "assignee" in allowed:
                fields["assignee"] = {"accountId": role_users[role]["accountId"]}

            created = client.create_issue(fields)
            issue_key = created["key"]
            assignee_tag = role or "Unassigned"
            print(f"  [CREATE] {issue['code']} -> {issue_key} [{assignee_tag} | {issue['story_points']} SP]: {issue['summary'][:65]}")

            # Best-effort post-create update if Story Points or Start Date were hidden on Create screen
            extra_update: dict[str, Any] = {}
            if story_field_id and story_field_id not in allowed and issue.get("story_points") is not None:
                extra_update[story_field_id] = issue["story_points"]
            if start_field_id and start_field_id not in allowed and issue.get("start_date"):
                extra_update[start_field_id] = issue["start_date"]
            if extra_update:
                try:
                    client.update_issue(issue_key, extra_update)
                except JiraApiError:
                    pass

            if issue.get("on_hold"):
                tr = client.try_transition(issue_key, ("On Hold", "Paused", "Tạm ngưng"))
                if tr:
                    print(f"           -> Đã chuyển trạng thái sang '{tr}'")

        issue_key_by_code[issue["code"]] = issue_key
        if sp_code and sp_code in issues_per_sprint:
            issues_per_sprint[sp_code].append(issue_key)

        for idx, (title, url) in enumerate(issue["github_links"], start=1):
            client.add_remote_link(issue_key, f"{seed_id}-link-{idx}", title, url)

    # 4. Assign active issues to their Sprints
    print(f"\n== Bước 4/4: Đưa Issues vào đúng {len(target_sprints)} Sprints ==")
    for sp in target_sprints:
        keys = issues_per_sprint[sp["code"]]
        client.move_issues_to_sprint(sprint_id_by_code[sp["code"]], keys)
        print(f"  [SPRINT] {sp['code']} (id={sprint_id_by_code[sp['code']]}): đã gán {len(keys)} issues.")

    # Export member checklist with live clickable URLs
    write_member_checklist(checklist_out, site_url, project_key, issue_key_by_code, role_users)
    print(f"\nHOÀN TẤT! Checklist kèm link Jira thật đã được xuất tại:\n  {checklist_out}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Đồng bộ kế hoạch dự án IDIR lên Jira Cloud qua REST API.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env.jira",
        help="Đường dẫn file cấu hình Jira cục bộ (mặc định: .env.jira ở root repo).",
    )
    parser.add_argument(
        "--checklist-out",
        type=Path,
        default=REPO_ROOT / "outputs" / "jira_member_checklists.md",
        help="Đường dẫn xuất file Checklist cho 5 thành viên.",
    )
    parser.add_argument(
        "--only-role",
        choices=("TV1", "TV2", "TV3", "TV4", "TV5"),
        default=None,
        help="Chỉ xử lý các thẻ của 1 thành viên cụ thể (không tạo/chạm vào thẻ người khác).",
    )
    parser.add_argument(
        "--sprint",
        choices=("S1", "S2", "S3", "S4", "S5"),
        default=None,
        help="Tùy chọn lọc chỉ 1 Sprint cụ thể (S1..S5).",
    )
    parser.add_argument(
        "--complete-my-tasks",
        action="store_true",
        help="Chỉ kéo trạng thái (In Progress -> In Review -> Done) và bình luận bằng chứng cho các thẻ của chính tài khoản bạn (bắt buộc dùng kèm --only-role).",
    )
    parser.add_argument(
        "--check-connection",
        action="store_true",
        help="Kiểm tra kết nối Jira, phát hiện Board/Fields và liệt kê thành viên trong Project.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chạy thử không gọi ghi lên Jira; in thống kê và danh sách thẻ sẽ xử lý.",
    )
    return parser.parse_args()


def main() -> int:
    configure_console_utf8()
    args = parse_args()
    env_values = load_env_file(args.env_file)

    site_url = get_setting(env_values, "JIRA_BASE_URL")
    email = get_setting(env_values, "JIRA_EMAIL")
    token = get_setting(env_values, "JIRA_API_TOKEN")
    project_key = get_setting(env_values, "JIRA_PROJECT_KEY", "IDIR")

    if args.dry_run:
        return run_dry_run(
            site_url,
            project_key,
            args.checklist_out,
            only_role=args.only_role,
            sprint_code=args.sprint,
            complete_my_tasks=args.complete_my_tasks,
        )

    missing = [
        name
        for name, val in (
            ("JIRA_BASE_URL", site_url),
            ("JIRA_EMAIL", email),
            ("JIRA_API_TOKEN", token),
            ("JIRA_PROJECT_KEY", project_key),
        )
        if not val
    ]
    if missing:
        print(
            f"[ERROR] Thiếu cấu hình bắt buộc: {', '.join(missing)}.\n"
            f"Hãy copy 'tools/jira/jira_env.example' thành '{args.env_file}' và điền thông tin Jira của bạn.",
            file=sys.stderr,
        )
        return 2

    client = JiraClient(site_url, email, token)
    try:
        if args.check_connection:
            return run_check_connection(client, project_key, env_values)
        if args.complete_my_tasks:
            return run_complete_my_tasks(client, project_key, args.only_role, args.sprint)
        return run_live_sync(
            client,
            client.base_url,
            project_key,
            env_values,
            args.checklist_out,
            only_role=args.only_role,
            sprint_code=args.sprint,
        )
    except JiraApiError as exc:
        print(f"\n[JIRA API ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
