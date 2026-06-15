"""
老师助手 - 配置文件
====================
你只需要修改这个文件中的配置项即可使用。
"""

import os
from pathlib import Path

# ============================================================
# 项目路径（不要修改）
# ============================================================
BASE_DIR = Path(__file__).parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
VECTOR_STORE_DIR = BASE_DIR / "vector_store"

# ============================================================
# AI 模型配置（二选一）
# ============================================================

# --- 方案A：DeepSeek API（推荐，速度快，费用极低）---
USE_DEEPSEEK = True
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-c46a7c3f2d1b409b86d516c3e5cf9416")
DEEPSEEK_MODEL = "deepseek-chat"

# --- 方案B：Ollama 本地模型（完全免费，无需联网）---
USE_OLLAMA = False
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:3b"

# ============================================================
# 网页服务器配置
# ============================================================
WEB_HOST = "0.0.0.0"    # 允许外部设备访问
WEB_PORT = int(os.environ.get("PORT", 8000))  # 端口号（云平台可通过环境变量指定）

# ============================================================
# 知识库配置
# ============================================================
SIMILARITY_THRESHOLD = 0.08
RETRIEVAL_COUNT = 5
CHUNK_SIZE = 5000
CHUNK_OVERLAP = 200

# ============================================================
# 机器人回答风格（中文）
# ============================================================
BOT_PROMPT_ZH = """你是一个知识问答助手。下面是从知识库中检索到的内容，请据此回答问题。

【知识库内容】
{context}

【用户问题】
{question}

规则：
1. 只根据上面的知识库内容回答
2. 如果内容完整包含答案，请直接完整呈现，不要精简或遗漏
3. 如果没有相关信息，请说"未找到相关信息"
4. 回答时保留关键信息的完整性"""

# ============================================================
# 机器人回答风格（English）
# ============================================================
BOT_PROMPT_EN = """You are an experienced teacher assistant helping new teachers with their work.
The knowledge base below is in Chinese. Carefully read ALL of it - the information the user needs IS in this Chinese text. 
Find the information most relevant to the user's English question and translate the answer to English.

Rules:
1. Only answer based on the provided knowledge, do not make up information
2. READ THE CHINESE TEXT CAREFULLY - the answer is likely there even if it doesn't seem to match the English keywords exactly
3. If truly no relevant information exists in the Chinese text, say so honestly
4. Keep answers concise and practical

Conversation history:
{history}

【Knowledge Base Content (Chinese)】
{context}

Current question: {question}
"""

# ============================================================
# 管理密码（用于上传/删除知识库文件）
# ============================================================
ADMIN_PASSWORD = "WH0804"

# ============================================================
# 回复免责声明（显示在每条回复最前面）
# ============================================================
DISCLAIMER_ZH = "小助手刚上岗，回复仅供参考，有疑问欢迎联系上级和阿九~"
DISCLAIMER_EN = "Disclaimer: This AI assistant is new, answers are for reference only. Please contact your supervisor for confirmation."

# ============================================================
# 日志设置
# ============================================================
LOG_LEVEL = "INFO"
