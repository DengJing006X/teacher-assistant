"""
Generate monthly usage and governance reports.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
EVENTS_PATH = DATA_DIR / "analytics_events.jsonl"
PENDING_PATH = DATA_DIR / "pending_questions.jsonl"
CORRECTION_PATH = DATA_DIR / "correction_reports.jsonl"
GOVERNANCE_ACTIONS_PATH = DATA_DIR / "governance_actions.jsonl"
REPORT_DIR = DATA_DIR / "reports"
DATA_LABEL = "测试数据"


def load_events(month: str) -> list[dict]:
    return load_jsonl_by_month(EVENTS_PATH, month)


def load_jsonl_by_month(path: Path, month: str) -> list[dict]:
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        item_month = item.get("month") or (item.get("created_at") or item.get("timestamp") or "")[:7]
        if item_month == month:
            items.append(item)
    return items


def answer_status(answer_type: str, answered: bool) -> str:
    if answered:
        return "已答复"
    if answer_type == "unhit":
        return "未答复-待补正文"
    return "未答复"


def generate(month: str) -> Path:
    events = load_events(month)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / f"monthly_report_{month}.csv"
    detail_path = REPORT_DIR / f"interaction_detail_{month}.csv"
    governance_path = REPORT_DIR / f"governance_followup_{month}.csv"

    by_group = defaultdict(lambda: {"questions": 0, "answered": 0, "unhit": 0, "sensitive": 0, "teachers": set()})
    by_teacher = defaultdict(lambda: {"questions": 0, "answered": 0, "unhit": 0, "sensitive": 0, "group_name": "", "leader_name": "", "display_name": "", "employee_no": ""})
    by_answer_type = defaultdict(int)

    for event in events:
        group = event.get("group_name") or "未同步小组"
        sender = event.get("sender_key") or event.get("display_name") or "unknown"
        answered = bool(event.get("answered"))
        answer_type = event.get("answer_type") or ""

        by_group[group]["questions"] += 1
        by_group[group]["answered"] += 1 if answered else 0
        by_group[group]["unhit"] += 1 if answer_type == "unhit" else 0
        by_group[group]["sensitive"] += 1 if answer_type == "sensitive_block" else 0
        by_group[group]["teachers"].add(sender)

        by_teacher[sender]["questions"] += 1
        by_teacher[sender]["answered"] += 1 if answered else 0
        by_teacher[sender]["unhit"] += 1 if answer_type == "unhit" else 0
        by_teacher[sender]["sensitive"] += 1 if answer_type == "sensitive_block" else 0
        by_teacher[sender]["group_name"] = group
        by_teacher[sender]["leader_name"] = event.get("leader_name", "")
        by_teacher[sender]["display_name"] = event.get("display_name", "")
        by_teacher[sender]["employee_no"] = event.get("employee_no", "")
        by_answer_type[answer_type] += 1

    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["数据标识", DATA_LABEL])
        writer.writerow(["说明", "本报表包含测试过程数据，不代表正式上线效果；主口径为一条老师消息/问题记一次提问。"])
        writer.writerow([])
        writer.writerow(["总提问次数", len(events)])
        writer.writerow(["已答复数", sum(1 for event in events if event.get("answered"))])
        writer.writerow(["答复率", f"{(sum(1 for event in events if event.get('answered')) / len(events)):.2%}" if events else "0.00%"])
        writer.writerow(["未命中待补正文数", sum(1 for event in events if event.get("answer_type") == "unhit")])
        writer.writerow(["敏感拦截数", sum(1 for event in events if event.get("answer_type") == "sensitive_block")])
        writer.writerow([])
        writer.writerow(["答复类型", "次数"])
        for answer_type, count in sorted(by_answer_type.items()):
            writer.writerow([answer_type or "unknown", count])
        writer.writerow([])
        writer.writerow(["类型", "小组", "组长", "老师", "工号", "提问次数", "已答复数", "未命中数", "敏感拦截数", "答复率"])

        for group, stat in sorted(by_group.items()):
            rate = stat["answered"] / stat["questions"] if stat["questions"] else 0
            writer.writerow(["小组汇总", group, "", "", "", stat["questions"], stat["answered"], stat["unhit"], stat["sensitive"], f"{rate:.2%}"])

        for _, stat in sorted(by_teacher.items(), key=lambda kv: (kv[1]["group_name"], kv[1]["display_name"])):
            rate = stat["answered"] / stat["questions"] if stat["questions"] else 0
            writer.writerow(
                [
                    "老师明细",
                    stat["group_name"],
                    stat["leader_name"],
                    stat["display_name"],
                    stat["employee_no"],
                    stat["questions"],
                    stat["answered"],
                    stat["unhit"],
                    stat["sensitive"],
                    f"{rate:.2%}",
                ]
            )

    with detail_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "数据标识",
            "时间",
            "会话",
            "老师",
            "工号",
            "小组",
            "组长",
            "问题",
            "答复类型",
            "答复状态",
            "来源文件",
            "事件ID",
        ])
        for event in events:
            writer.writerow([
                event.get("data_label") or DATA_LABEL,
                event.get("timestamp", ""),
                event.get("conversation_title", ""),
                event.get("display_name", ""),
                event.get("employee_no", ""),
                event.get("group_name", ""),
                event.get("leader_name", ""),
                event.get("question", ""),
                event.get("answer_type", ""),
                answer_status(event.get("answer_type", ""), bool(event.get("answered"))),
                event.get("source_file", ""),
                event.get("event_id", ""),
            ])

    pending_items = load_jsonl_by_month(PENDING_PATH, month)
    correction_items = load_jsonl_by_month(CORRECTION_PATH, month)
    governance_actions = load_jsonl_by_month(GOVERNANCE_ACTIONS_PATH, month)
    action_by_id = defaultdict(list)
    for action in governance_actions:
        action_by_id[action.get("pending_id", "")].append(action.get("action", ""))

    with governance_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["类型", "ID", "状态", "创建时间", "责任部门", "负责人", "提问/反馈人", "小组", "问题", "错误说明", "已发生治理动作"])
        for item in pending_items:
            writer.writerow([
                "未命中待补充",
                item.get("pending_id", ""),
                item.get("status", ""),
                item.get("created_at", ""),
                item.get("owner", {}).get("department", ""),
                item.get("owner", {}).get("owner_name", ""),
                item.get("teacher", {}).get("display_name", ""),
                item.get("teacher", {}).get("group_name", ""),
                item.get("question", ""),
                "",
                "；".join(action_by_id.get(item.get("pending_id", ""), [])),
            ])
        for item in correction_items:
            writer.writerow([
                "答案纠错",
                item.get("correction_id", ""),
                item.get("status", ""),
                item.get("created_at", ""),
                item.get("owner", {}).get("department", ""),
                item.get("owner", {}).get("owner_name", ""),
                item.get("reporter", {}).get("display_name", ""),
                item.get("reporter", {}).get("group_name", ""),
                item.get("question", ""),
                item.get("error_description", ""),
                "；".join(action_by_id.get(item.get("correction_id", ""), [])),
            ])

    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python monthly_report.py YYYY-MM")
    print(generate(sys.argv[1]))
