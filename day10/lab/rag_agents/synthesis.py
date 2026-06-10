"""Grounded offline answer synthesis agent."""

from __future__ import annotations

import os
import re
from typing import Any, Dict


CAPABILITIES_ANSWER = """Tôi có thể giải đáp dựa trên 5 nhóm tài liệu đã được làm sạch:

1. Chính sách hoàn tiền: thời hạn, điều kiện, ngoại lệ, quy trình CS và Finance.
2. SLA sự cố P1: phản hồi, resolution, escalation và kênh thông báo.
3. IT Helpdesk: tài khoản, mật khẩu, VPN, email và laptop.
4. Chính sách HR: nghỉ phép năm, nghỉ ốm, remote work và thâm niên.
5. Access Control: các level quyền, người phê duyệt, thời gian xử lý và quyền khẩn cấp.

Bạn hãy hỏi một câu cụ thể trong các nhóm trên. Tôi sẽ trả lời kèm nguồn tài liệu."""


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"\w+", text.casefold(), flags=re.UNICODE) if len(token) > 1}


def _sentences(text: str) -> list[str]:
    text = text.split("|", 1)[-1].strip()
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _best_sentence(question: str, text: str) -> str:
    query = _tokens(question)
    choices = _sentences(text)
    if not choices:
        return text.strip()
    return max(
        choices,
        key=lambda sentence: (
            len(query & _tokens(sentence)),
            bool(re.search(r"\d", sentence)),
            len(sentence),
        ),
    )


def _gemini_answer(question: str, evidence: list[dict]) -> tuple[str, str]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "", ""

    from google import genai

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    context = "\n\n".join(
        f"[{index}] doc_id={item['doc_id']}; effective_date={item['effective_date']}\n{item['text']}"
        for index, item in enumerate(evidence[:5], 1)
    )
    prompt = f"""Bạn là trợ lý hỏi đáp tài liệu nội bộ.
Chỉ trả lời bằng context bên dưới, không dùng kiến thức ngoài.
Trả lời ngắn gọn bằng tiếng Việt và giữ citation dạng [1], [2].
Nếu context không đủ, trả lời: Không đủ thông tin trong tài liệu đã xử lý.

Câu hỏi: {question}

Context:
{context}
"""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return (response.text or "").strip(), model


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    if state.get("intent") == "capabilities":
        state["answer"] = CAPABILITIES_ANSWER
        state["citations"] = []
        state["synthesis_provider"] = "system_capabilities"
        state["synthesis_model"] = ""
        state["confidence"] = 1.0
        state["needs_human_review"] = False
        state["workers_called"].append("synthesis_agent")
        state["events"].append(
            {
                "agent": "synthesis_agent",
                "provider": "system_capabilities",
                "model": "",
                "confidence": 1.0,
                "needs_human_review": False,
            }
        )
        return state

    evidence = state.get("evidence", [])
    if not evidence:
        state["answer"] = "Không đủ thông tin đáng tin cậy trong tài liệu đã xử lý để trả lời."
        state["citations"] = []
        state["confidence"] = 0.0
        state["needs_human_review"] = True
    else:
        answer_parts = []
        citations = []
        max_evidence = 2 if len(state.get("domain_filters", [])) > 1 else 1
        for index, item in enumerate(evidence[:max_evidence], 1):
            answer_parts.append(f"{_best_sentence(state['question'], item['text'])} [{index}]")
            citations.append(
                {
                    "index": index,
                    "doc_id": item["doc_id"],
                    "effective_date": item["effective_date"],
                    "chunk_id": item["chunk_id"],
                    "score": item["score"],
                }
            )
        provider = "offline_extractive"
        model = ""
        try:
            gemini_answer, model = _gemini_answer(state["question"], evidence)
            if gemini_answer:
                state["answer"] = gemini_answer
                provider = "gemini"
            else:
                state["answer"] = " ".join(answer_parts)
        except Exception as exc:
            state["errors"].append(f"synthesis_agent Gemini fallback: {type(exc).__name__}: {exc}")
            state["answer"] = " ".join(answer_parts)
        state["citations"] = citations
        state["synthesis_provider"] = provider
        state["synthesis_model"] = model
        best_score = evidence[0]["score"]
        source_bonus = min(0.1, len({item["doc_id"] for item in evidence}) * 0.02)
        guard_penalty = 0.15 if state.get("rejected_evidence") else 0.0
        state["confidence"] = round(max(0.0, min(0.98, best_score + source_bonus - guard_penalty)), 2)
        state["needs_human_review"] = state["risk_high"] or state["confidence"] < 0.35

    state["workers_called"].append("synthesis_agent")
    state["events"].append(
        {
            "agent": "synthesis_agent",
            "provider": state.get("synthesis_provider", "offline_extractive"),
            "model": state.get("synthesis_model", ""),
            "confidence": state["confidence"],
            "needs_human_review": state["needs_human_review"],
        }
    )
    return state
