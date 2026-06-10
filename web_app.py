"""
老师助手 - Web 网页版
======================
在微信里打开链接就能用的 AI 问答助手，支持中英双语。
支持网页上传知识库文件，适合部署到云端。

启动方式: python web_app.py
"""

import sys
import logging
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import config as app_config
from knowledge_base import KnowledgeBase
from llm_engine import LLMEngine

logging.basicConfig(
    level=getattr(logging, app_config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("web_app")

from fastapi import FastAPI, Request, UploadFile, File, Header
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="老师助手 Teacher Assistant")

# 全局变量
kb: KnowledgeBase = None
llm: LLMEngine = None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    language: str = "zh"
    history: list = []


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    language: str


def reload_knowledge_base():
    global kb
    new_kb = KnowledgeBase(app_config)
    new_kb.initialize()
    kb = new_kb


@app.on_event("startup")
async def startup():
    global kb, llm
    logger.info("正在初始化知识库...")
    kb = KnowledgeBase(app_config)
    kb.initialize()
    doc_count = kb.get_document_count()
    chunk_count = kb.get_chunk_count()
    if doc_count > 0:
        logger.info(f"知识库就绪: {doc_count} 个文档, {chunk_count} 个文本片段")
    else:
        logger.warning("knowledge 文件夹为空，请上传文档")

    logger.info("正在连接 AI 模型...")
    llm = LLMEngine(app_config)
    ok, msg = llm.check_connection()
    if ok:
        logger.info(f"AI 模型就绪: {msg}")
    else:
        logger.warning(f"AI 模型异常: {msg}")

    logger.info("=" * 40)
    logger.info(f"启动地址: http://localhost:{app_config.WEB_PORT}")
    logger.info("在微信/浏览器中打开即可使用")
    if app_config.WEB_HOST == "0.0.0.0":
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        logger.info(f"局域网地址: http://{local_ip}:{app_config.WEB_PORT}")
    logger.info("=" * 40)


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "templates" / "chat.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return HTMLResponse("<h1>老师助手</h1><p>页面加载失败</p>")


@app.post("/api/chat")
async def chat(req: ChatRequest):
    global kb, llm

    if kb is None or llm is None:
        return ChatResponse(
            session_id=req.session_id or "",
            reply="系统正在初始化，请稍后再试" if req.language == "zh" else "System is initializing, please try again later",
            language=req.language,
        )

    session_id = req.session_id or uuid.uuid4().hex[:8]
    question = req.message.strip()
    lang = req.language if req.language in ("zh", "en") else "zh"

    if not question:
        return ChatResponse(
            session_id=session_id,
            reply="请输入您的问题" if lang == "zh" else "Please enter your question",
            language=lang,
        )

    logger.info(f"[{session_id}] ({lang}) 提问: {question}")

    # 知识库检索
    results = kb.search(question)
    if results:
        context = "\n\n---\n\n".join(
            f"[来自: {f}]\n{c}" for c, _, f in results
        )
        logger.info(f"检索到 {len(results)} 个相关片段")
    else:
        context = ""

    # AI 回答
    try:
        answer = llm.ask(
            question=question,
            context=context,
            language=lang,
            history=req.history,
        )
    except Exception as e:
        logger.error(f"AI 回答失败: {e}")
        answer = (
            "抱歉，AI 暂时无法回答，请稍后再试"
            if lang == "zh"
            else "Sorry, AI is unavailable. Please try again later."
        )

    logger.info(f"[{session_id}] 回答: {answer[:80]}...")
    return ChatResponse(
        session_id=session_id,
        reply=answer,
        language=lang,
    )


@app.get("/api/health")
async def health():
    status = "ok"
    issues = []
    if kb is None:
        status = "error"
        issues.append("知识库未初始化")
    if llm is None:
        status = "error"
        issues.append("AI模型未初始化")
    doc_count = kb.get_document_count() if kb else 0
    return {
        "status": status,
        "documents": doc_count,
        "issues": issues,
    }


# ============================================================
# 管理员验证
# ============================================================

def check_admin(x_admin_password: str = Header(None)):
    if x_admin_password != app_config.ADMIN_PASSWORD:
        return False
    return True


@app.post("/api/verify-password")
async def verify_password(x_admin_password: str = Header(None)):
    if x_admin_password == app_config.ADMIN_PASSWORD:
        return {"ok": True}
    return JSONResponse(status_code=403, content={"error": "密码错误"})


# ============================================================
# 文件管理 API
# ============================================================

@app.get("/api/files")
async def list_files(x_admin_password: str = Header(None)):
    """列出知识库中的所有文件"""
    if x_admin_password != app_config.ADMIN_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "密码错误"})
    knowdir = app_config.KNOWLEDGE_DIR
    knowdir.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(knowdir.glob("*")):
        if f.suffix.lower() in (".txt", ".md"):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
            })
    return {"files": files}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), x_admin_password: str = Header(None)):
    """上传知识库文件"""
    if x_admin_password != app_config.ADMIN_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "密码错误"})
    knowdir = app_config.KNOWLEDGE_DIR
    knowdir.mkdir(parents=True, exist_ok=True)

    if not file.filename.lower().endswith((".txt", ".md")):
        return JSONResponse(
            status_code=400,
            content={"error": "仅支持 .txt 和 .md 文件"},
        )

    filepath = knowdir / file.filename
    content = await file.read()
    filepath.write_bytes(content)

    reload_knowledge_base()

    doc_count = kb.get_document_count()
    logger.info(f"文件 {file.filename} 上传成功，共 {doc_count} 个文档")
    return {
        "message": f"{file.filename} 上传成功",
        "documents": doc_count,
    }


@app.delete("/api/files/{filename}")
async def delete_file(filename: str, x_admin_password: str = Header(None)):
    """删除知识库中的文件"""
    if x_admin_password != app_config.ADMIN_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "密码错误"})
    import urllib.parse
    filename = urllib.parse.unquote(filename)
    filepath = app_config.KNOWLEDGE_DIR / filename

    if not filepath.exists():
        return JSONResponse(
            status_code=404,
            content={"error": f"文件 {filename} 不存在"},
        )

    filepath.unlink()
    reload_knowledge_base()

    doc_count = kb.get_document_count()
    logger.info(f"文件 {filename} 已删除，共 {doc_count} 个文档")
    return {
        "message": f"{filename} 已删除",
        "documents": doc_count,
    }


@app.post("/api/reload")
async def reload_kb(x_admin_password: str = Header(None)):
    """手动重新加载知识库"""
    if x_admin_password != app_config.ADMIN_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "密码错误"})
    reload_knowledge_base()
    doc_count = kb.get_document_count()
    return {"message": "知识库已重新加载", "documents": doc_count}


def main():
    uvicorn.run(
        app,
        host=app_config.WEB_HOST,
        port=app_config.WEB_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
