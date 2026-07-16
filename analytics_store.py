"""
Operational logging, governance workflow, and approved KB write-back.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


TEST_DATA_LABEL = "测试数据"
DEFAULT_OWNER_EMPLOYEE_NO = "WH0804"
DEFAULT_OWNER_USER_ID = "0104205445101186080"
DEFAULT_OWNER_DISPLAY_NAME = "阿九"

PUBLIC_LEVEL = "public"
WHITELIST_LEVEL = "functional_whitelist"
SENSITIVE_LEVEL = "sensitive_review"


@dataclass
class AnswerRecord:
    event_id: str
    timestamp: str
    month: str
    question: str
    answer_type: str
    answered: bool
    sender_key: str
    sender_nick: str
    sender_staff_id: str
    sender_id: str
    employee_no: str
    display_name: str
    group_name: str
    leader_name: str
    conversation_id: str
    conversation_title: str
    source_file: str = ""
    data_label: str = TEST_DATA_LABEL


class AnalyticsStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.events_path = self.data_dir / "analytics_events.jsonl"
        self.pending_path = self.data_dir / "pending_questions.jsonl"
        self.draft_answers_path = self.data_dir / "draft_answers.jsonl"
        self.correction_reports_path = self.data_dir / "correction_reports.jsonl"
        self.correction_drafts_path = self.data_dir / "correction_drafts.jsonl"
        self.governance_actions_path = self.data_dir / "governance_actions.jsonl"
        self.teacher_directory_path = self.data_dir / "teacher_directory.json"
        self.owner_routes_path = self.data_dir / "owner_routes.json"
        self.governance_channel_path = self.data_dir / "governance_channel.json"

        self.public_kb_path = self.base_dir / "knowledge" / "教学" / "审核通过-公开可答知识库.md"
        self.whitelist_kb_path = self.base_dir / "knowledge" / "职能白名单" / "审核通过-职能白名单知识库.md"
        self.sensitive_kb_path = self.base_dir / "knowledge" / "敏感待审核" / "审核通过-敏感暂不回答知识库.md"

        self._ensure_seed_files()

    def save_governance_channel(self, message) -> dict[str, str]:
        payload = {
            "conversation_id": getattr(message, "conversation_id", "") or "",
            "conversation_title": getattr(message, "conversation_title", "") or "",
            "session_webhook": getattr(message, "session_webhook", "") or "",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.governance_channel_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload

    def get_governance_webhook(self) -> str:
        config = self._load_json(self.governance_channel_path)
        return config.get("custom_webhook") or config.get("session_webhook", "")

    def get_governance_secret(self) -> str:
        return self._load_json(self.governance_channel_path).get("custom_secret", "")

    def save_governance_custom_webhook(self, webhook: str, secret: str = "") -> dict[str, str]:
        config = self._load_json(self.governance_channel_path)
        config["custom_webhook"] = webhook
        config["custom_secret"] = secret
        config["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.governance_channel_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return config

    def _ensure_seed_files(self):
        if not self.teacher_directory_path.exists():
            self.teacher_directory_path.write_text(
                json.dumps(
                    {
                        "description": "用 DingTalk sender_staff_id 或 sender_id 作为临时键；拿到通讯录权限后补 employee_no、display_name、group_name、leader_name。",
                        "teachers": {},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        if not self.owner_routes_path.exists():
            self.owner_routes_path.write_text(
                json.dumps(default_owner_routes(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _load_json(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        items = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
        return items

    def resolve_sender(self, message) -> dict[str, str]:
        sender_staff_id = getattr(message, "sender_staff_id", "") or ""
        sender_id = getattr(message, "sender_id", "") or ""
        sender_nick = getattr(message, "sender_nick", "") or ""

        directory = self._load_json(self.teacher_directory_path).get("teachers", {})
        profile = directory.get(sender_staff_id) or directory.get(sender_id) or {}

        employee_no = profile.get("employee_no", "")
        display_name = (
            profile.get("display_name")
            or sender_nick
            or employee_no
            or sender_staff_id
            or sender_id
            or "unknown"
        )
        sender_key = employee_no or sender_staff_id or sender_id or display_name

        return {
            "sender_key": sender_key,
            "sender_nick": sender_nick,
            "sender_staff_id": sender_staff_id,
            "sender_id": sender_id,
            "employee_no": employee_no,
            "display_name": display_name,
            "group_name": profile.get("group_name", "未同步小组"),
            "leader_name": profile.get("leader_name", "未同步组长"),
        }

    def _append_jsonl(self, path: Path, payload: dict[str, Any]):
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def record_question(
        self,
        *,
        message,
        question: str,
        answer_type: str,
        answered: bool,
        source_file: str = "",
    ) -> AnswerRecord:
        now = datetime.now()
        sender = self.resolve_sender(message)
        record = AnswerRecord(
            event_id=str(uuid.uuid4()),
            timestamp=now.isoformat(timespec="seconds"),
            month=now.strftime("%Y-%m"),
            question=question,
            answer_type=answer_type,
            answered=answered,
            conversation_id=getattr(message, "conversation_id", "") or "",
            conversation_title=getattr(message, "conversation_title", "") or "",
            source_file=source_file,
            **sender,
        )
        self._append_jsonl(self.events_path, asdict(record))
        return record

    def route_owner(self, question: str) -> dict[str, str]:
        config = self._load_json(self.owner_routes_path) or default_owner_routes()
        lowered = question.lower()
        for route in config.get("routes", []):
            for keyword in route.get("keywords", []):
                if keyword.lower() in lowered:
                    return route
        return config.get("default_owner", {})

    def record_pending_question(self, record: AnswerRecord, question: str) -> dict[str, Any]:
        owner = self.route_owner(question)
        payload = {
            "pending_id": record.event_id,
            "status": "待补充/待分配",
            "created_at": record.timestamp,
            "question": question,
            "data_label": TEST_DATA_LABEL,
            "teacher": {
                "sender_key": record.sender_key,
                "display_name": record.display_name,
                "employee_no": record.employee_no,
                "group_name": record.group_name,
            },
            "owner": {
                "department": owner.get("department", "组织建设"),
                "owner_name": owner.get("owner_name") or DEFAULT_OWNER_DISPLAY_NAME,
                "employee_no": owner.get("employee_no") or DEFAULT_OWNER_EMPLOYEE_NO,
                "user_id": owner.get("user_id") or DEFAULT_OWNER_USER_ID,
            },
            "workflow": [
                "写入待补充/待分配",
                "推送负责人",
                "负责人指定填充正文或审核人选",
                "人选处理",
                "负责人人工审核",
                "审核通过后按分级写入知识库",
            ],
        }
        self._append_jsonl(self.pending_path, payload)
        self.notify_owner(owner, payload)
        return payload

    def build_governance_notice(self, payload: dict[str, Any]) -> str:
        pending_id = payload["pending_id"]
        question = payload["question"]
        department = payload["owner"]["department"]
        teacher_name = payload["teacher"]["display_name"]
        group_name = payload["teacher"]["group_name"]

        return (
            "【知识库待补充】\n"
            f"问题ID：#{pending_id}\n"
            f"负责人：{DEFAULT_OWNER_DISPLAY_NAME}\n"
            f"责任部门：{department}\n"
            f"提问老师：{teacher_name}\n"
            f"小组：{group_name}\n"
            f"问题：{question}\n\n"
            "处理方式：\n"
            "注意：在群里处理时，需要先 @海外教学小助手，机器人才能收到指令。\n\n"
            f"1. 补正文：补充正文 #{pending_id}\n"
            "结论：\n流程：\n材料：\n提醒：\n\n"
            f"2. 分配给别人：分配处理 #{pending_id} 处理人：姓名 说明：原因\n"
            f"3. 审核通过并入公开知识库：审核通过 #{pending_id}\n"
            f"4. 审核通过但仅职能白名单可答：审核通过 #{pending_id} 白名单\n"
            f"5. 审核通过但判定为敏感暂不答：审核通过 #{pending_id} 敏感"
        )

    def notify_owner(self, owner: dict[str, str], payload: dict[str, Any]):
        webhook = owner.get("webhook", "")
        if not webhook:
            return
        try:
            requests.post(
                webhook,
                json={"msgtype": "text", "text": {"content": self.build_governance_notice(payload)}},
                timeout=10,
            ).raise_for_status()
        except Exception:
            return

    def handle_governance_command(self, message, text: str) -> str:
        text = text.strip()
        if text.startswith("补充正文"):
            return self._record_draft_answer(message, text)
        if text.startswith("更新正文"):
            return self._record_correction_draft(message, text)
        if text.startswith("分配处理"):
            return self._record_assignment(message, text)
        if text.startswith("审核通过"):
            return self._record_approval(message, text)
        if text.startswith("审核更新"):
            return self._record_update_approval(message, text)
        return ""

    def record_correction_report(self, message, text: str) -> dict[str, Any]:
        sender = self.resolve_sender(message)
        parsed = self._parse_correction_report(text)
        owner = self.route_owner(parsed["question"])
        payload = {
            "correction_id": str(uuid.uuid4()),
            "status": "待纠错",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "data_label": TEST_DATA_LABEL,
            "question": parsed["question"],
            "error_description": parsed["error_description"],
            "reporter": sender,
            "source": {
                "conversation_id": getattr(message, "conversation_id", "") or "",
                "conversation_title": getattr(message, "conversation_title", "") or "",
            },
            "owner": {
                "department": owner.get("department", "组织建设"),
                "owner_name": owner.get("owner_name") or DEFAULT_OWNER_DISPLAY_NAME,
                "employee_no": owner.get("employee_no") or DEFAULT_OWNER_EMPLOYEE_NO,
                "user_id": owner.get("user_id") or DEFAULT_OWNER_USER_ID,
            },
        }
        self._append_jsonl(self.correction_reports_path, payload)
        return payload

    def build_correction_notice(self, payload: dict[str, Any]) -> str:
        correction_id = payload["correction_id"]
        return (
            "【知识库待纠错】\n"
            f"纠错ID：#{correction_id}\n"
            f"负责人：{DEFAULT_OWNER_DISPLAY_NAME}\n"
            f"责任部门：{payload['owner']['department']}\n"
            f"反馈人：{payload['reporter']['display_name']}\n"
            f"来源会话：{payload['source']['conversation_title']}\n"
            f"原问题：{payload['question']}\n"
            f"错误说明：{payload['error_description']}\n\n"
            "处理方式：\n"
            "1. 更新正文：\n"
            f"更新正文 #{correction_id}\n"
            "结论：\n流程：\n材料：\n提醒：\n\n"
            f"2. 审核更新并进入公开知识库：审核更新 #{correction_id}\n"
            f"3. 审核更新但仅职能白名单可答：审核更新 #{correction_id} 白名单\n"
            f"4. 审核更新但判定为敏感暂不答：审核更新 #{correction_id} 敏感"
        )

    def _parse_correction_report(self, text: str) -> dict[str, str]:
        content = re.sub(r"^(纠错|答案有误)[:：]?\s*", "", text.strip())
        parts = re.split(r"错误说明[:：]", content, maxsplit=1)
        question = parts[0].strip() or "未填写原问题"
        error_description = parts[1].strip() if len(parts) > 1 else "未填写错误说明"
        return {"question": question, "error_description": error_description}

    def _extract_pending_id(self, text: str) -> str:
        match = re.search(r"#([0-9a-fA-F-]{8,})", text)
        return match.group(1) if match else ""

    def _record_draft_answer(self, message, text: str) -> str:
        pending_id = self._extract_pending_id(text)
        if not pending_id:
            return "没有识别到问题ID。请按格式发送：补充正文 #问题ID"

        sender = self.resolve_sender(message)
        payload = {
            "draft_id": str(uuid.uuid4()),
            "pending_id": pending_id,
            "status": "待负责人审核",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "data_label": TEST_DATA_LABEL,
            "operator": sender,
            "content": text,
            "parsed_answer": self._parse_answer_sections(text),
        }
        self._append_jsonl(self.draft_answers_path, payload)
        return (
            f"已收到 #{pending_id} 的补充正文，状态：待负责人审核。\n\n"
            "【负责人审核提醒】\n"
            f"负责人：{DEFAULT_OWNER_DISPLAY_NAME}\n"
            "请先判断这版正文的分级：公开可答 / 职能白名单 / 敏感暂不答。\n"
            f"公开可答：审核通过 #{pending_id}\n"
            f"职能白名单：审核通过 #{pending_id} 白名单\n"
            f"敏感暂不答：审核通过 #{pending_id} 敏感"
        )

    def _record_correction_draft(self, message, text: str) -> str:
        correction_id = self._extract_pending_id(text)
        if not correction_id:
            return "没有识别到纠错ID。请按格式发送：更新正文 #纠错ID"

        sender = self.resolve_sender(message)
        payload = {
            "draft_id": str(uuid.uuid4()),
            "correction_id": correction_id,
            "status": "待负责人审核",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "data_label": TEST_DATA_LABEL,
            "operator": sender,
            "content": text,
            "parsed_answer": self._parse_answer_sections(text, command="更新正文"),
        }
        self._append_jsonl(self.correction_drafts_path, payload)
        return (
            f"已收到 #{correction_id} 的更新正文，状态：待负责人审核。\n\n"
            "【负责人审核提醒】\n"
            f"负责人：{DEFAULT_OWNER_DISPLAY_NAME}\n"
            "请先判断新版正文的分级：公开可答 / 职能白名单 / 敏感暂不答。\n"
            f"公开可答：审核更新 #{correction_id}\n"
            f"职能白名单：审核更新 #{correction_id} 白名单\n"
            f"敏感暂不答：审核更新 #{correction_id} 敏感"
        )

    def _record_assignment(self, message, text: str) -> str:
        pending_id = self._extract_pending_id(text)
        if not pending_id:
            return "没有识别到问题ID。请按格式发送：分配处理 #问题ID 处理人：姓名 说明：原因"

        payload = self._action_payload(message, pending_id, "分配处理", text)
        self._append_jsonl(self.governance_actions_path, payload)
        return f"已记录 #{pending_id} 的分配处理信息。"

    def _record_approval(self, message, text: str) -> str:
        pending_id = self._extract_pending_id(text)
        if not pending_id:
            return "没有识别到问题ID。请按格式发送：审核通过 #问题ID"

        draft = self._find_latest_draft(pending_id)
        pending = self._find_pending(pending_id)
        if not draft:
            return f"没有找到 #{pending_id} 的补充正文，不能入库。请先补充正文。"

        access_level = self._classify_access_level(text, draft.get("content", ""))
        kb_path = self._write_approved_knowledge(pending_id, pending, draft, access_level)

        payload = self._action_payload(message, pending_id, f"审核通过:{access_level}", text)
        payload["kb_path"] = str(kb_path)
        self._append_jsonl(self.governance_actions_path, payload)

        if access_level == PUBLIC_LEVEL:
            return f"已记录 #{pending_id} 审核通过，并已写入公开可答知识库。"
        if access_level == WHITELIST_LEVEL:
            return f"已记录 #{pending_id} 审核通过，并已写入职能白名单知识库。测试版普通老师暂不可答。"
        return f"已记录 #{pending_id} 审核通过，并已写入敏感暂不回答板块。机器人不会对老师直接回答。"

    def _record_update_approval(self, message, text: str) -> str:
        correction_id = self._extract_pending_id(text)
        if not correction_id:
            return "没有识别到纠错ID。请按格式发送：审核更新 #纠错ID"

        draft = self._find_latest_correction_draft(correction_id)
        report = self._find_correction_report(correction_id)
        if not draft:
            return f"没有找到 #{correction_id} 的更新正文，不能更新知识库。请先发送更新正文。"

        access_level = self._classify_access_level(text, draft.get("content", ""))
        kb_path = self._write_correction_knowledge(correction_id, report, draft, access_level)

        payload = self._action_payload(message, correction_id, f"审核更新:{access_level}", text)
        payload["kb_path"] = str(kb_path)
        self._append_jsonl(self.governance_actions_path, payload)

        if access_level == PUBLIC_LEVEL:
            return f"已记录 #{correction_id} 审核更新，并已写入公开可答知识库。旧答案已通过历史块保留。"
        if access_level == WHITELIST_LEVEL:
            return f"已记录 #{correction_id} 审核更新，并已写入职能白名单知识库。测试版普通老师暂不可答。"
        return f"已记录 #{correction_id} 审核更新，并已写入敏感暂不回答板块。机器人不会对老师直接回答。"

    def _action_payload(self, message, pending_id: str, action: str, text: str) -> dict[str, Any]:
        return {
            "action_id": str(uuid.uuid4()),
            "pending_id": pending_id,
            "action": action,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "data_label": TEST_DATA_LABEL,
            "operator": self.resolve_sender(message),
            "content": text,
        }

    def _find_latest_draft(self, pending_id: str) -> dict[str, Any]:
        drafts = [item for item in self._read_jsonl(self.draft_answers_path) if item.get("pending_id") == pending_id]
        return drafts[-1] if drafts else {}

    def _find_latest_correction_draft(self, correction_id: str) -> dict[str, Any]:
        drafts = [item for item in self._read_jsonl(self.correction_drafts_path) if item.get("correction_id") == correction_id]
        return drafts[-1] if drafts else {}

    def _find_pending(self, pending_id: str) -> dict[str, Any]:
        for item in reversed(self._read_jsonl(self.pending_path)):
            if item.get("pending_id") == pending_id:
                return item
        return {}

    def _find_correction_report(self, correction_id: str) -> dict[str, Any]:
        for item in reversed(self._read_jsonl(self.correction_reports_path)):
            if item.get("correction_id") == correction_id:
                return item
        return {}

    def _classify_access_level(self, approval_text: str, draft_text: str) -> str:
        combined = f"{approval_text}\n{draft_text}"
        if any(keyword in combined for keyword in ["敏感", "暂不答", "处罚", "绩效", "薪酬", "工资", "申诉", "审批结果", "判责"]):
            return SENSITIVE_LEVEL
        if any(keyword in combined for keyword in ["白名单", "职能", "仅负责人", "仅管理", "不可公开"]):
            return WHITELIST_LEVEL
        return PUBLIC_LEVEL

    def _parse_answer_sections(self, text: str, command: str = "补充正文") -> dict[str, str]:
        content = re.sub(rf"^{command}\s*#[0-9a-fA-F-]{{8,}}\s*", "", text.strip())
        headings = ["结论", "流程", "材料", "提醒"]
        sections = {heading: "" for heading in headings}
        pattern = r"(结论|流程|材料|提醒)[:：]"
        matches = list(re.finditer(pattern, content))
        for index, match in enumerate(matches):
            heading = match.group(1)
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            sections[heading] = content[start:end].strip()
        return sections

    def _write_correction_knowledge(
        self,
        correction_id: str,
        report: dict[str, Any],
        draft: dict[str, Any],
        access_level: str,
    ) -> Path:
        pending_like = {
            "question": report.get("question") or "未记录原问题",
            "owner": report.get("owner", {}),
        }
        sections = draft.get("parsed_answer") or self._parse_answer_sections(draft.get("content", ""), command="更新正文")
        if access_level == WHITELIST_LEVEL:
            path = self.whitelist_kb_path
        elif access_level == SENSITIVE_LEVEL:
            path = self.sensitive_kb_path
        else:
            path = self.public_kb_path

        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            self._write_approved_knowledge(correction_id, pending_like, draft, access_level)
            return path

        question = pending_like["question"]
        department = pending_like.get("owner", {}).get("department", "未分配")
        block = (
            f"\n## {question}\n\n"
            f"<!-- correction_id: {correction_id}; access_level: {access_level}; department: {department}; updated_at: {datetime.now().isoformat(timespec='seconds')} -->\n\n"
            f"**结论：**\n{sections.get('结论') or '无'}\n\n"
            f"**流程：**\n{sections.get('流程') or '无'}\n\n"
            f"**材料：**\n{sections.get('材料') or '无'}\n\n"
            f"**提醒：**\n{sections.get('提醒') or '无'}\n"
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(block)
        return path

    def _write_approved_knowledge(
        self,
        pending_id: str,
        pending: dict[str, Any],
        draft: dict[str, Any],
        access_level: str,
    ) -> Path:
        if access_level == WHITELIST_LEVEL:
            path = self.whitelist_kb_path
        elif access_level == SENSITIVE_LEVEL:
            path = self.sensitive_kb_path
        else:
            path = self.public_kb_path

        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            title = {
                PUBLIC_LEVEL: "# 审核通过-公开可答知识库\n\n",
                WHITELIST_LEVEL: "# 审核通过-职能白名单知识库\n\n> 仅供白名单角色读取，测试版不对普通老师开放。\n\n",
                SENSITIVE_LEVEL: "# 审核通过-敏感暂不回答知识库\n\n> 该板块仅做归档和治理，不对老师直接回答。\n\n",
            }[access_level]
            path.write_text(title, encoding="utf-8")

        question = pending.get("question") or "未记录原问题"
        department = pending.get("owner", {}).get("department", "未分配")
        sections = draft.get("parsed_answer") or self._parse_answer_sections(draft.get("content", ""))
        block = (
            f"\n## {question}\n\n"
            f"<!-- pending_id: {pending_id}; access_level: {access_level}; department: {department}; approved_at: {datetime.now().isoformat(timespec='seconds')} -->\n\n"
            f"**结论：**\n{sections.get('结论') or '无'}\n\n"
            f"**流程：**\n{sections.get('流程') or '无'}\n\n"
            f"**材料：**\n{sections.get('材料') or '无'}\n\n"
            f"**提醒：**\n{sections.get('提醒') or '无'}\n"
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(block)
        return path


def default_owner_routes() -> dict[str, Any]:
    owner = {
        "owner_name": DEFAULT_OWNER_DISPLAY_NAME,
        "employee_no": DEFAULT_OWNER_EMPLOYEE_NO,
        "user_id": DEFAULT_OWNER_USER_ID,
        "webhook": "",
    }
    return {
        "description": "未命中问题负责人路由。测试阶段所有部门负责人统一为 WH0804，对外展示阿九。",
        "default_owner": {"department": "组织建设", **owner},
        "routes": [
            {"department": "考勤小姐姐", "keywords": ["考勤", "签到", "迟到", "旷课", "请假", "排班"], **owner},
            {"department": "IT服务台", "keywords": ["账号", "密码", "登录", "系统", "设备", "网络", "钉钉"], **owner},
            {"department": "教学-demo组", "keywords": ["demo", "Demo", "试听"], **owner},
            {"department": "教学-粤语教学", "keywords": ["粤语"], **owner},
            {"department": "教学-台湾教学", "keywords": ["台湾"], **owner},
            {"department": "教学-英语教学", "keywords": ["英语"], **owner},
            {"department": "教学-外教教学", "keywords": ["外教"], **owner},
            {"department": "教学", "keywords": ["上课", "课件", "学生", "学员", "班级", "课程", "补课", "顺延"], **owner},
            {"department": "中台-排课教务", "keywords": ["排课", "调课", "代课", "插班"], **owner},
            {"department": "中台-数据运营", "keywords": ["数据", "报表", "统计", "指标"], **owner},
            {"department": "中台-新师培训", "keywords": ["新师", "入职", "培训", "主备", "述职", "竞聘", "转岗"], **owner},
            {"department": "中台-组织建设", "keywords": ["OA", "流程", "银行卡", "工资卡", "组织", "离职", "孕期", "福利"], **owner},
        ],
    }
