"""
Teacher Assistant - shared configuration for H5 and DingTalk test version
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
VECTOR_STORE_DIR = BASE_DIR / "vector_store"


# ============================================================
# DingTalk application
# ============================================================
DINGTALK_APP_ID = os.environ.get("DINGTALK_APP_ID", "")
DINGTALK_AGENT_ID = os.environ.get("DINGTALK_AGENT_ID", "")
DINGTALK_CLIENT_ID = os.environ.get("DINGTALK_CLIENT_ID", "")
DINGTALK_CLIENT_SECRET = os.environ.get("DINGTALK_CLIENT_SECRET", "")
DINGTALK_CORP_ID = os.environ.get("DINGTALK_CORP_ID", "")


# ============================================================
# Model configuration
# ============================================================
USE_DEEPSEEK = True
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

USE_OLLAMA = False
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")


# ============================================================
# Web server
# ============================================================
WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("PORT", 8000))


# ============================================================
# Test-mode rules
# ============================================================
TEST_MODE = True
ALLOWED_KNOWLEDGE_CATEGORIES = ["教学", "制度"]
MAX_HISTORY_MESSAGES = 10

SIMILARITY_THRESHOLD = 0.10
RETRIEVAL_COUNT = 5
CHUNK_SIZE = 5000
CHUNK_OVERLAP = 200

SENSITIVE_KEYWORDS = [
    "薪酬",
    "工资",
    "奖金",
    "绩效",
    "扣绩效",
    "扣款",
    "处罚",
    "红线",
    "申诉能不能过",
    "申诉结果",
    "审批结果",
    "转正能不能过",
    "晋升能不能过",
    "淘汰",
    "离职审批",
    "后台",
    "内部表",
    "内部台账",
    "周报",
    "日会",
    "个人信息",
    "身份证",
    "银行卡密码",
    "访问密码",
]

TEST_SCOPE_NOTICE_ZH = (
    "当前为测试版，仅覆盖一线老师知识库和已确认可公开的公司通用知识。"
    "不回答薪酬、绩效、处罚、审批结果、申诉结果、内部台账等敏感问题。"
)
TEST_SCOPE_NOTICE_EN = (
    "This is a test version. It only covers frontline teacher knowledge and approved company-wide common knowledge. "
    "Sensitive topics such as payroll, performance, penalties, approval outcomes, appeal outcomes, and internal records are not answered."
)

UNHIT_REPLY_ZH = (
    "这个问题当前知识库里还没有可直接回答的已确认答案，我先帮你记为待补充问题。\n"
    "如果比较紧急，请先联系直属负责人或对应教务/职能负责人处理。"
)
UNHIT_REPLY_EN = (
    "The current knowledge base does not yet have a confirmed answer for this question.\n"
    "If it is urgent, please contact your supervisor or the relevant teaching or functional owner first."
)

SENSITIVE_REPLY_ZH = (
    "这个问题涉及敏感信息、审批结果或个案判断，我暂时不能直接给最终结论。\n"
    "请联系直属负责人或对应负责人确认；如果你愿意，我可以先帮你整理需要说明的材料。"
)
SENSITIVE_REPLY_EN = (
    "This question involves sensitive information, approval outcomes, or case-by-case judgment, so I cannot provide a final conclusion directly.\n"
    "Please confirm with your supervisor or the relevant owner first."
)


# ============================================================
# Prompts
# ============================================================
BOT_PROMPT_ZH = """你是“老师小助手”测试版，只能根据给定知识回答问题。
【测试范围】{scope_notice}

【知识库内容】{context}

【用户问题】{question}

请严格遵守：
1. 只能基于给定知识回答，不得补充未给出的制度、结论或承诺。
2. 优先使用以下结构回答：结论、流程、材料、提醒。
3. 不要让用户自己去找文档。
4. 不要回答薪酬、绩效、处罚、审批结果、申诉结果、内部链接、后台表格。
5. 如果上下文不足以支持回答，直接返回：{unhit_reply}
6. 回答保持简短，优先直接解决问题，不要重复整段知识原文。
"""

BOT_PROMPT_EN = """You are the test version of "Teacher Assistant" and may only answer from the provided knowledge.

Test scope:
{scope_notice}

Conversation history:
{history}

Knowledge base content:
{context}

Current question:
{question}

Rules:
1. Answer only from the provided knowledge.
2. Prefer this structure: Conclusion, Steps, Materials, Reminder.
3. Do not tell the user to search documents by themselves.
4. Do not answer payroll, performance, penalties, approval outcomes, appeal outcomes, internal links, or internal records.
5. If the context is insufficient, return exactly: {unhit_reply}
6. Keep the answer concise and avoid dumping the full source text.
"""


# ============================================================
# Admin / UI
# ============================================================
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WH0804")

DISCLAIMER_ZH = (
    "当前为测试版，回答仅供参考；如涉及审批、判责或敏感事项，请联系直属负责人确认。"
)
DISCLAIMER_EN = (
    "This is a test version. Answers are for reference only. "
    "For approvals, judgment, or sensitive matters, please confirm with your supervisor."
)


# ============================================================
# Logging
# ============================================================
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
