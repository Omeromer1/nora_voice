import os
import re
from typing import List, Dict, Any

try:
    from docx import Document as DocxDocument
except Exception as e:
    raise RuntimeError("python-docx غير مثبت. ثبّته عبر: pip install python-docx") from e


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _tokenize_ar(text: str) -> List[str]:
    # تبسيط عربي خفيف (بدون مكتبات إضافية)
    text = _clean(text).lower()
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه")  # تقارب لغرض البحث فقط
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    toks = [t for t in text.split() if len(t) > 2]
    return toks


def _load_kb_paragraphs(path: str) -> List[str]:
    d = DocxDocument(path)
    paras = []
    for p in d.paragraphs:
        t = _clean(p.text)
        if t:
            paras.append(t)
    return paras


def _best_match(question: str, paras: List[str]) -> Dict[str, Any]:
    q_toks = set(_tokenize_ar(question))
    if not q_toks:
        return {"score": 0, "text": ""}

    best = {"score": 0, "text": ""}
    for para in paras:
        p_toks = set(_tokenize_ar(para))
        if not p_toks:
            continue
        score = len(q_toks.intersection(p_toks))
        if score > best["score"]:
            best = {"score": score, "text": para}

    return best


# ------ Function exposed to the Deepgram Agent ------
_KB_CACHE = {"path": None, "paras": None}

def kb_answer(question: str) -> Dict[str, Any]:
    """
    KB-only answer function.
    Returns: {found: bool, answer: str, source: str}
    """
    kb_path = os.getenv("KB_DOCX_PATH", "PSAU_Knowledge_Base.docx")

    if _KB_CACHE["path"] != kb_path or _KB_CACHE["paras"] is None:
        if not os.path.exists(kb_path):
            return {
                "found": False,
                "answer": "قاعدة المعرفة غير موجودة حالياً على الخادم.",
                "source": kb_path
            }
        _KB_CACHE["path"] = kb_path
        _KB_CACHE["paras"] = _load_kb_paragraphs(kb_path)

    paras = _KB_CACHE["paras"] or []
    match = _best_match(question, paras)

    # عتبة بسيطة: لازم على الأقل 2 كلمة مشتركة
    if match["score"] < int(os.getenv("KB_MIN_OVERLAP", "2")):
        return {
            "found": False,
            "answer": "ما لقيت معلومة كافية في قاعدة المعرفة للإجابة بدقة.",
            "source": kb_path
        }

    # لو الفقرة طويلة، قصّها عشان الصوت يكون لطيف
    ans = match["text"]
    max_chars = int(os.getenv("KB_MAX_CHARS", "600"))
    if len(ans) > max_chars:
        ans = ans[:max_chars].rsplit(" ", 1)[0] + "…"

    return {
        "found": True,
        "answer": ans,
        "source": kb_path
    }


FUNCTION_MAP = {
    "kb_answer": kb_answer
}
