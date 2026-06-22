"""
Teacher Assistant - H5 test version
"""

import logging
import sys
import uuid
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

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

app = FastAPI(title="Teacher Assistant H5 Test")

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


class PasswordBody(BaseModel):
    password: str


def format_fallback_answer(question: str, results: list, language: str) -> str:
    top_chunks = [chunk for chunk, _, _ in results[:3]]
    top_files = []
    for _, _, filename in results[:3]:
        if filename not in top_files:
            top_files.append(filename)

    if language == "en":
        intro = "The AI service is temporarily unavailable. Based on the current approved knowledge, here is a fallback answer for reference."
        conclusion = f"Conclusion:\nYour question is related to the currently loaded knowledge base: {question}"
        steps = "Steps:\n1. Follow the relevant process described below.\n2. If your case needs approval or judgment, contact your supervisor.\n3. If the information is still insufficient, use the manual escalation path."
        materials = "Materials:\n1. Keep screenshots, class time, class name, and a short explanation if relevant.\n2. Prepare any records mentioned below before contacting a supervisor."
        reminder = "Reminder:\nThis is a fallback answer generated without the model. If the issue involves approval, penalties, performance, or case judgment, please confirm with the responsible owner."
        knowledge = "Relevant knowledge excerpts:\n" + "\n\n".join(top_chunks)
        sources = "Sources:\n- " + "\n- ".join(top_files)
        return "\n\n".join([intro, conclusion, steps, materials, reminder, knowledge, sources])

    intro = "AI 服务暂时不可用。基于当前已确认知识，我先给你一版兜底参考答案。"
    conclusion = f"结论：\n你这个问题与当前知识库已有内容相关，建议先按下面的流程处理。"
    steps = "流程：\n1. 先参考下方匹配到的知识内容执行。\n2. 如果涉及审批、判责或个案判断，及时联系直属负责人确认。\n3. 如果下方信息仍不足以覆盖你的场景，走人工确认。"
    materials = "材料：\n1. 如涉及课程问题，请保留课程时间、班级、截图和情况说明。\n2. 如涉及流程问题，请准备需要提交的基础信息和记录。"
    reminder = "提醒：\n这是一版无模型兜底答案，不代表最终审批或判定结论；涉及绩效、处罚、申诉、审批结果等内容，仍需负责人确认。"
    knowledge = "匹配到的知识内容：\n" + "\n\n".join(top_chunks)
    sources = "来源文件：\n- " + "\n- ".join(top_files)
    return "\n\n".join([intro, conclusion, steps, materials, reminder, knowledge, sources])


def is_sensitive_question(question: str) -> bool:
    lowered = question.lower()
    for keyword in app_config.SENSITIVE_KEYWORDS:
        if keyword.lower() in lowered:
            return True
    return False


def reload_knowledge_base():
    global kb
    new_kb = KnowledgeBase(app_config)
    new_kb.initialize()
    kb = new_kb


@app.on_event("startup")
async def startup():
    global kb, llm
    logger.info("Initializing H5 test version knowledge base...")
    kb = KnowledgeBase(app_config)
    kb.initialize()
    logger.info("Knowledge base ready: %s docs / %s chunks", kb.get_document_count(), kb.get_chunk_count())

    logger.info("Connecting AI model...")
    llm = LLMEngine(app_config)
    ok, msg = llm.check_connection()
    if ok:
        logger.info(msg)
    else:
        logger.warning(msg)


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "templates" / "chat.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return HTMLResponse("<h1>Teacher Assistant</h1><p>Page load failed.</p>")


@app.get("/api/health")
async def health():
    return {
        "status": "ok" if kb is not None and llm is not None else "error",
        "documents": kb.get_document_count() if kb else 0,
        "chunks": kb.get_chunk_count() if kb else 0,
        "test_mode": app_config.TEST_MODE,
        "allowed_categories": app_config.ALLOWED_KNOWLEDGE_CATEGORIES,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    global kb, llm

    lang = req.language if req.language in ("zh", "en") else "zh"
    session_id = req.session_id or uuid.uuid4().hex[:8]
    question = req.message.strip()

    if not question:
        return ChatResponse(
            session_id=session_id,
            reply="请输入您的问题。" if lang == "zh" else "Please enter your question.",
            language=lang,
        )

    if kb is None or llm is None:
        return ChatResponse(
            session_id=session_id,
            reply="系统正在初始化，请稍后再试。" if lang == "zh" else "System is initializing, please try again later.",
            language=lang,
        )

    logger.info("[%s][%s] question: %s", session_id, lang, question)

    if is_sensitive_question(question):
        reply = app_config.SENSITIVE_REPLY_ZH if lang == "zh" else app_config.SENSITIVE_REPLY_EN
        reply = f"{app_config.DISCLAIMER_ZH if lang == 'zh' else app_config.DISCLAIMER_EN}\n\n{reply}"
        return ChatResponse(session_id=session_id, reply=reply, language=lang)

    results = kb.search(question)
    if not results:
        reply = app_config.UNHIT_REPLY_ZH if lang == "zh" else app_config.UNHIT_REPLY_EN
        reply = f"{app_config.DISCLAIMER_ZH if lang == 'zh' else app_config.DISCLAIMER_EN}\n\n{reply}"
        return ChatResponse(session_id=session_id, reply=reply, language=lang)

    context = "\n\n---\n\n".join(f"[来源: {filename}]\n{chunk}" for chunk, _, filename in results)

    try:
        answer = llm.ask(
            question=question,
            context=context,
            language=lang,
            history=req.history[-app_config.MAX_HISTORY_MESSAGES:],
        )
    except Exception as e:
        logger.error("Answer generation failed: %s", e)
        answer = format_fallback_answer(question, results, lang)

    disclaimer = app_config.DISCLAIMER_ZH if lang == "zh" else app_config.DISCLAIMER_EN
    answer = f"{disclaimer}\n\n{answer}"
    return ChatResponse(session_id=session_id, reply=answer, language=lang)


@app.post("/api/verify-password")
async def verify_password(body: PasswordBody):
    if body.password == app_config.ADMIN_PASSWORD:
        return {"ok": True}
    return JSONResponse(status_code=403, content={"error": "密码错误"})


@app.get("/api/files")
async def list_files(t: str = ""):
    if t != app_config.ADMIN_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "密码错误"})

    knowdir = app_config.KNOWLEDGE_DIR
    knowdir.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(knowdir.glob("**/*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".txt", ".md"):
            continue
        relative = f.relative_to(knowdir)
        category = relative.parent.name if relative.parent.name != "." else ""
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "category": category,
        })
    return {"files": files}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), t: str = "", category: str = ""):
    if t != app_config.ADMIN_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "密码错误"})

    if not file.filename.lower().endswith((".txt", ".md")):
        return JSONResponse(status_code=400, content={"error": "仅支持 .txt 和 .md 文件"})

    knowdir = app_config.KNOWLEDGE_DIR
    if category:
        knowdir = knowdir / category
    knowdir.mkdir(parents=True, exist_ok=True)

    filepath = knowdir / file.filename
    content = await file.read()
    filepath.write_bytes(content)

    reload_knowledge_base()
    return {"message": f"{file.filename} 上传成功", "documents": kb.get_document_count()}


@app.delete("/api/files/{filename}")
async def delete_file(filename: str, t: str = "", category: str = ""):
    if t != app_config.ADMIN_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "密码错误"})

    import urllib.parse

    decoded = urllib.parse.unquote(filename)
    knowdir = app_config.KNOWLEDGE_DIR
    if category:
        knowdir = knowdir / category
    filepath = knowdir / decoded

    if not filepath.exists():
        return JSONResponse(status_code=404, content={"error": f"文件 {decoded} 不存在"})

    filepath.unlink()
    reload_knowledge_base()
    return {"message": f"{decoded} 已删除", "documents": kb.get_document_count()}


@app.post("/api/reload")
async def reload_kb(t: str = ""):
    if t != app_config.ADMIN_PASSWORD:
        return JSONResponse(status_code=403, content={"error": "密码错误"})

    reload_knowledge_base()
    return {"message": "知识库已重新加载", "documents": kb.get_document_count()}


def main():
    uvicorn.run(
        app,
        host=app_config.WEB_HOST,
        port=app_config.WEB_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
