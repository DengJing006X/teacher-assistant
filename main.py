"""
Teacher Assistant - DingTalk bot test version.
"""

from __future__ import annotations

import logging
import base64
import hashlib
import hmac
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import config as app_config
from analytics_store import DEFAULT_OWNER_USER_ID, AnalyticsStore
from faq_bank import lookup_faq_answer
from knowledge_base import KnowledgeBase
from llm_engine import LLMEngine


logging.basicConfig(
    level=getattr(logging, app_config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dingtalk_bot")


@dataclass
class BotAnswer:
    text: str
    answer_type: str
    answered: bool
    source_file: str = ""


def is_sensitive_question(question: str) -> bool:
    lowered = question.lower()
    return any(keyword.lower() in lowered for keyword in app_config.SENSITIVE_KEYWORDS)


def clean_lines(text: str) -> list[str]:
    raw_lines = [line.strip() for line in text.splitlines()]
    cleaned = []
    for line in raw_lines:
        if not line:
            continue
        line = re.sub(r"^[>\-*\d\.\、\s]+", "", line).strip()
        line = line.replace("**", "").strip()
        if line.startswith("##"):
            line = line[2:].strip()
        cleaned.append(line)
    return cleaned


def normalize_heading(line: str) -> str | None:
    normalized = line.strip().replace("：", ":")
    if normalized in {"结论", "结论:"}:
        return "结论"
    if normalized in {"流程", "流程:"}:
        return "流程"
    if normalized in {"材料", "材料:"}:
        return "材料"
    if normalized in {"提醒", "提醒:"}:
        return "提醒"
    return None


def extract_section_blocks(lines: list[str]) -> dict[str, list[str]]:
    blocks = {"结论": [], "流程": [], "材料": [], "提醒": []}
    current = None

    for line in lines:
        heading = normalize_heading(line)
        if heading:
            current = heading
            continue
        if current:
            blocks[current].append(line)
    return blocks


def compact_block(lines: list[str], limit: int) -> list[str]:
    compacted = []
    for line in lines:
        if line and not is_empty_section_line(line):
            compacted.append(line)
        if len(compacted) >= limit:
            break
    return compacted


def is_empty_section_line(line: str) -> bool:
    normalized = re.sub(r"^[\d\.\、\s]+", "", line).strip()
    normalized = normalized.strip("。；;，, ")
    return normalized in {"无", "暂无", "没有", "无内容", "不需要"}


def format_numbered(lines: list[str]) -> list[str]:
    output = []
    for index, line in enumerate(lines, start=1):
        cleaned = re.sub(r"^\d+[\.\、]\s*", "", line).strip()
        output.append(f"{index}. {cleaned}")
    return output


def format_answer_text(text: str) -> str:
    lines = clean_lines(text)
    blocks = extract_section_blocks(lines)
    output: list[str] = []

    conclusion_lines = compact_block(blocks["结论"], 3)
    if conclusion_lines:
        output.append("结论：")
        output.extend(conclusion_lines)

    process_lines = compact_block(blocks["流程"], 3)
    if process_lines:
        if output:
            output.append("")
        output.append("流程：")
        output.extend(format_numbered(process_lines))

    material_lines = compact_block(blocks["材料"], 3)
    if material_lines:
        if output:
            output.append("")
        output.append("材料：")
        output.extend(format_numbered(material_lines))

    reminder_lines = compact_block(blocks["提醒"], 2)
    if reminder_lines:
        if output:
            output.append("")
        output.append("提醒：")
        output.extend(reminder_lines)

    if not output:
        output = compact_block(lines, 6)

    return "\n".join(output).strip()


def unhit_answer() -> str:
    return "这个问题当前还没有已确认答案，已记录为待补充。"


def sensitive_answer() -> str:
    return "这个问题涉及敏感信息、审批结果或个案判断，我暂时不能直接给结论。请联系直属负责人或对应负责人确认。"


def send_plain_text(incoming_message, text: str, at_user_ids: list[str] | None = None):
    payload = {
        "msgtype": "text",
        "text": {
            "content": text,
        },
    }
    if at_user_ids:
        payload["at"] = {
            "atUserIds": at_user_ids,
            "isAtAll": False,
        }
    response = requests.post(incoming_message.session_webhook, json=payload, timeout=10)
    response.raise_for_status()


def signed_dingtalk_webhook(webhook: str, secret: str = "") -> str:
    if not secret:
        return webhook
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    separator = "&" if "?" in webhook else "?"
    return f"{webhook}{separator}timestamp={timestamp}&sign={sign}"


def send_text_to_webhook(webhook: str, text: str, at_user_ids: list[str] | None = None, secret: str = ""):
    payload = {
        "msgtype": "text",
        "text": {
            "content": text,
        },
    }
    if at_user_ids:
        payload["at"] = {
            "atUserIds": at_user_ids,
            "isAtAll": False,
        }
    response = requests.post(signed_dingtalk_webhook(webhook, secret), json=payload, timeout=10)
    response.raise_for_status()


def is_governance_command(text: str) -> bool:
    return text.strip().startswith(("补充正文", "更新正文", "分配处理", "审核通过", "审核更新"))


def is_correction_report_command(text: str) -> bool:
    return text.strip().startswith(("纠错", "答案有误"))


def is_set_governance_channel_command(text: str) -> bool:
    return text.strip() in {"设置治理群", "设为治理群", "设置知识库治理群"}


def needs_owner_at(text: str) -> bool:
    return "知识库待补充" in text or "负责人审核提醒" in text


class TeacherBot:
    """DingTalk teacher assistant bot for the test version."""

    def __init__(self):
        self.config = app_config
        self.analytics = AnalyticsStore(BASE_DIR)
        self.knowledge_base = KnowledgeBase(self.config)
        self.llm = LLMEngine(self.config)

    def check_setup(self) -> list[str]:
        issues = []
        if not self.config.DINGTALK_CLIENT_ID:
            issues.append("缺少 DINGTALK_CLIENT_ID")
        if not self.config.DINGTALK_CLIENT_SECRET:
            issues.append("缺少 DINGTALK_CLIENT_SECRET")

        kb_path = self.config.KNOWLEDGE_DIR
        md_txt_files = list(kb_path.glob("**/*.md")) + list(kb_path.glob("**/*.txt"))
        if not md_txt_files:
            issues.append(f"knowledge 目录为空: {kb_path}")
        return issues

    def process_question(self, question: str) -> BotAnswer:
        question = question.strip()
        if not question:
            return BotAnswer("请输入具体问题。", "empty", True)

        if is_sensitive_question(question):
            return BotAnswer(sensitive_answer(), "sensitive_block", True)

        faq_answer = lookup_faq_answer(question)
        if faq_answer:
            return BotAnswer(faq_answer, "faq", True)

        results = self.knowledge_base.search(question)
        if not results:
            return BotAnswer(unhit_answer(), "unhit", False)

        context = "\n\n---\n\n".join(f"[来源: {filename}]\n{chunk}" for chunk, _, filename in results)
        top_chunk, _, source_file = results[0]

        try:
            answer = self.llm.ask(
                question=question,
                context=context,
                language="zh",
                history=[],
            )
            return BotAnswer(format_answer_text(answer), "knowledge_llm", True, source_file)
        except Exception as e:
            logger.error("Answer generation failed: %s", e)
            return BotAnswer(format_answer_text(top_chunk), "knowledge_fallback", True, source_file)

    def initialize(self) -> bool:
        issues = self.check_setup()
        if issues:
            logger.error("配置检查发现问题：")
            for issue in issues:
                logger.error("  - %s", issue)
            return False

        logger.info("正在初始化知识库...")
        self.knowledge_base.initialize()
        logger.info(
            "知识库就绪: %s 个文档 / %s 个片段",
            self.knowledge_base.get_document_count(),
            self.knowledge_base.get_chunk_count(),
        )

        logger.info("正在测试 AI 模型连接...")
        ok, msg = self.llm.check_connection()
        if ok:
            logger.info("AI 模型连接通过: %s", msg)
        else:
            logger.warning("AI 模型连接失败，将使用知识库兜底: %s", msg)
        return True

    def run(self):
        if not self.initialize():
            return

        logger.info("=" * 50)
        logger.info("正在连接钉钉 Stream...")
        logger.info("机器人已启动，等待消息...")
        logger.info("=" * 50)

        try:
            import dingtalk_stream
        except ImportError:
            logger.error("缺少 dingtalk-stream 依赖，请安装: pip install dingtalk-stream")
            return

        bot = self

        class TeacherChatbotHandler(dingtalk_stream.ChatbotHandler):
            async def process(self, callback_message):
                try:
                    message = dingtalk_stream.ChatbotMessage.from_dict(callback_message.data)
                    question = " ".join(message.get_text_list() or []).strip()
                    sender = message.sender_nick or message.sender_staff_id or message.sender_id or "unknown"

                    if is_set_governance_channel_command(question):
                        channel = bot.analytics.save_governance_channel(message)
                        send_plain_text(message, f"已设置当前群为知识库治理群：{channel.get('conversation_title') or '当前群'}")
                        logger.info("已设置治理群 [%s]", channel.get("conversation_title"))
                        return dingtalk_stream.AckMessage.STATUS_OK, "OK"

                    if is_governance_command(question):
                        reply = bot.analytics.handle_governance_command(message, question)
                        if question.strip().startswith(("审核通过", "审核更新")):
                            bot.knowledge_base.initialize()
                        at_user_ids = [DEFAULT_OWNER_USER_ID] if reply and needs_owner_at(reply) else None
                        send_plain_text(message, reply or "治理指令未识别。", at_user_ids=at_user_ids)
                        logger.info("已处理治理指令 [%s]", sender)
                        return dingtalk_stream.AckMessage.STATUS_OK, "OK"

                    if is_correction_report_command(question):
                        correction_payload = bot.analytics.record_correction_report(message, question)
                        send_plain_text(message, "已记录为待纠错，负责人会在治理群核对。")
                        governance_webhook = bot.analytics.get_governance_webhook()
                        if governance_webhook:
                            send_text_to_webhook(
                                governance_webhook,
                                bot.analytics.build_correction_notice(correction_payload),
                                at_user_ids=[DEFAULT_OWNER_USER_ID],
                                secret=bot.analytics.get_governance_secret(),
                            )
                        else:
                            logger.warning("未设置治理群，跳过纠错通知推送")
                        logger.info("已记录纠错 [%s]", sender)
                        return dingtalk_stream.AckMessage.STATUS_OK, "OK"

                    logger.info("来自 [%s] 的消息: %s", sender, question)
                    answer = bot.process_question(question)

                    record = bot.analytics.record_question(
                        message=message,
                        question=question,
                        answer_type=answer.answer_type,
                        answered=answer.answered,
                        source_file=answer.source_file,
                    )
                    pending_payload = None
                    if answer.answer_type == "unhit":
                        pending_payload = bot.analytics.record_pending_question(record, question)

                    send_plain_text(message, answer.text)
                    if pending_payload:
                        governance_webhook = bot.analytics.get_governance_webhook()
                        if governance_webhook:
                            send_text_to_webhook(
                                governance_webhook,
                                bot.analytics.build_governance_notice(pending_payload),
                                at_user_ids=[DEFAULT_OWNER_USER_ID],
                                secret=bot.analytics.get_governance_secret(),
                            )
                        else:
                            logger.warning("未设置治理群，跳过治理通知推送")

                    logger.info("已回复 [%s], type=%s", sender, answer.answer_type)
                    return dingtalk_stream.AckMessage.STATUS_OK, "OK"
                except Exception as e:
                    logger.error("处理消息失败: %s", e, exc_info=True)
                    return dingtalk_stream.AckMessage.STATUS_SYSTEM_EXCEPTION, "system error"

        try:
            credential = dingtalk_stream.Credential(
                self.config.DINGTALK_CLIENT_ID,
                self.config.DINGTALK_CLIENT_SECRET,
            )
            client = dingtalk_stream.DingTalkStreamClient(credential)
            client.register_callback_handler(
                dingtalk_stream.ChatbotMessage.TOPIC,
                TeacherChatbotHandler(),
            )
            client.start_forever()
        except Exception as e:
            logger.error("启动机器人失败: %s", e, exc_info=True)


def main():
    TeacherBot().run()


if __name__ == "__main__":
    main()
