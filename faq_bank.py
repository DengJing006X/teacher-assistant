"""
FAQ fast-path answers for the teacher assistant.

This layer is intentionally small and deterministic:
- exact / near-exact common questions
- short answers with only non-empty sections
- used before KB retrieval and LLM fallback
"""

from __future__ import annotations

import re


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return text


def _format_sections(*sections: tuple[str, list[str] | None]) -> str:
    parts: list[str] = []
    for title, lines in sections:
        clean_lines = [line.strip() for line in (lines or []) if line and line.strip()]
        if not clean_lines:
            continue
        parts.append(f"{title}：")
        parts.extend(clean_lines)
    return "\n".join(parts).strip()


FAQ_ENTRIES = [
    {
        "patterns": [
            "临时不能上课怎么办",
            "不能上课怎么办",
            "临时不能上课",
        ],
        "answer": _format_sections(
            ("结论", [
                "分“24小时以上”和“24小时以内”两种情况处理。先找代课，再协调插班或补课；实在无法协调，再申请顺延。",
            ]),
            ("流程", [
                "1. 提前24小时以上知道不能上课，先在群里找代课老师。",
                "2. 找不到代课时，查是否有同时段、同进度班级可插班；没有的话再和家长协调补课时间。",
                "3. 如果是24小时内的紧急情况，优先联系直属上级协助处理。",
            ]),
            ("材料", [
                "1. 找代课老师的沟通截图。",
                "2. 和家长协调补课时间的记录。",
                "3. 如需顺延，保留经理同意截图。",
            ]),
            ("提醒", [
                "24小时内的紧急课程不要自己硬扛，优先找上级协助。",
            ]),
        ),
    },
    {
        "patterns": [
            "学员考勤状态点错了怎样修改",
            "考勤状态点错了怎样修改",
            "考勤点错了怎么改",
        ],
        "answer": _format_sections(
            ("结论", [
                "先区分是不是老师原因。老师原因可以走 OA 修改；不是老师原因的，通常要联系班主任处理。",
            ]),
            ("流程", [
                "1. 先确认是老师操作失误，还是家长网络、家长主动退出等其他原因。",
                "2. 如果是老师原因，老师自己在端口走 OA 申请修改。",
                "3. 如果不是老师原因，联系班主任，由班主任跟进邮件申请。",
            ]),
            ("材料", [
                "1. 课堂记录截图。",
                "2. OA 申请记录或班主任邮件记录。",
                "3. 异常情况说明。",
            ]),
            ("提醒", [
                "学员进入课堂超过15分钟后，系统会自动签到；非老师原因时，老师自行申请通常会被驳回。",
            ]),
        ),
    },
    {
        "patterns": [
            "非招商银行卡可以发薪吗",
            "招商银行卡发薪吗",
            "银行卡发薪",
        ],
        "answer": _format_sections(
            ("结论", [
                "可以，一般不要求必须使用招商银行卡发薪。",
            ]),
            ("流程", [
                "1. 先确认你当前在系统里填写的银行卡信息是否正确。",
                "2. 如果需要更换银行卡，按公司要求走信息更新流程。",
                "3. 更新后留意后续发薪是否正常到账。",
            ]),
            ("材料", [
                "1. 银行卡基础信息。",
                "2. 如有变更，提供对应更新材料。",
            ]),
            ("提醒", [
                "如果涉及到账异常、金额异常或补发判断，这类问题仍需负责人确认。",
            ]),
        ),
    },
]


def lookup_faq_answer(question: str) -> str:
    normalized_question = _normalize(question)
    if not normalized_question:
        return ""

    for entry in FAQ_ENTRIES:
        for pattern in entry["patterns"]:
            normalized_pattern = _normalize(pattern)
            if normalized_pattern and (
                normalized_pattern in normalized_question
                or normalized_question in normalized_pattern
            ):
                return entry["answer"]
    return ""
