"""
Teacher Assistant - H5 test version
"""

import logging
import sys
import urllib.parse
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


def extract_direct_answer(text: str, question: str) -> str:
    lines = text.splitlines()
    normalized_question = question.replace("？", "").replace("?", "").strip()

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## ") and normalized_question in stripped.replace("？", "").replace("?", ""):
            section = [stripped]
            for next_line in lines[idx + 1:]:
                if next_line.strip().startswith("## "):
                    break
                section.append(next_line.rstrip())
            return "\n".join(section).strip()

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            section = [stripped]
            for next_line in lines[idx + 1:]:
                if next_line.strip().startswith("## "):
                    break
                section.append(next_line.rstrip())
            return "\n".join(section).strip()

    return text.strip()


def shorten_answer_block(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    kept = []
    current_section = None
    section_counts = {
        "流程": 0,
        "材料": 0,
        "提醒": 0,
    }

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if kept and kept[-1] != "":
                kept.append("")
            continue

        if stripped.startswith("## "):
            title = stripped[3:].strip()
            if title.startswith("临时不能上课怎么办") or title.startswith("被排了非工作时间段课程") or title.startswith("学员考勤状态点错了"):
                kept.append(f"问题：{title}")
            continue

        if stripped.startswith("**结论：**") or stripped == "结论：":
            current_section = "结论"
            kept.append("结论：")
            continue
        if stripped.startswith("**流程：**") or stripped == "流程：":
            current_section = "流程"
            kept.append("流程：")
            continue
        if stripped.startswith("**材料：**") or stripped == "材料：":
            current_section = "材料"
            kept.append("材料：")
            continue
        if stripped.startswith("**提醒：**") or stripped == "提醒：":
            current_section = "提醒"
            kept.append("提醒：")
            continue

        if current_section == "结论":
            if not kept or kept[-1] == "结论：":
                kept.append(stripped.replace("**", ""))
            continue

        if current_section in ("流程", "材料"):
            if stripped[:2].isdigit() or (len(stripped) > 1 and stripped[0].isdigit() and stripped[1] == "."):
                if section_counts[current_section] < 3:
                    kept.append(stripped.replace("**", ""))
                    section_counts[current_section] += 1
            continue

        if current_section == "提醒":
            if section_counts["提醒"] < 2:
                kept.append(stripped.replace("**", ""))
                section_counts["提醒"] += 1
            continue

    compact = "\n".join(line for line in kept if line is not None).strip()
    if len(compact) > 700:
        compact = compact[:700].rstrip()
    return compact


def format_fallback_answer(question: str, results: list, language: str) -> str:
    top_chunk, _, _ = results[0]
    section = extract_direct_answer(top_chunk, question)
    short_answer = shorten_answer_block(section)

    if language == "en":
        return "The AI service is temporarily unavailable. Here is the closest confirmed answer:\n\n" + short_answer

    return "AI 服务暂时不可用。先给你当前知识库里最接近的一版直接答案：\n\n" + short_answer


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

    decoded = urllib.parse.unquote(filename)
    knowdir = app_config.KNOWLEDGE_DIR
    if category:
        knowdir = knowdir / category
    filepath = knowdir / decoded

    if not filepath.exists():
        return JSONResponse(status_code=404, content={"error": "文件不存在"})

    filepath.unlink()
    reload_knowledge_base()
    return {"message": f"{decoded} 删除成功", "documents": kb.get_document_count()}


if __name__ == "__main__":
    uvicorn.run("web_app:app", host=app_config.WEB_HOST, port=app_config.WEB_PORT, reload=False)
