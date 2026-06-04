"""LLM 批量注音 —— 一次请求处理整首歌词。

参考 StrangeUtaGame/llm_ruby.py 的设计，但去掉 GUI/WinRT 依赖，改为独立模块。
返回 {line_idx: [(surface, hira_reading)]}，surface 连接必须等于原行。
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

Pairs = List[Tuple[str, str]]  # (surface, hira_reading)

_SYSTEM_PROMPT = (
    "あなたは日本語の注音（ふりがな）エンジンです。"
    "与えられた歌詞を行ごとに分かち書きし、各トークンに平仮名の読みを付けます。"
    "規則：(1) 漢字を含むトークンの読みは平仮名で。"
    "(2) 仮名・記号・英数字のトークンの読みは原文そのまま。"
    "(3) 各行のトークンの surface を連結すると元の行と完全に一致すること。"
    "(4) JSON のみを出力し、説明文を一切付けないこと。"
)

_SCHEMA_HINT = (
    '出力フォーマット（JSON のみ）：\n'
    '{"lines":[{"i":0,"tokens":[{"s":"今日","r":"きょう"},{"s":"は","r":"は"}]}]}\n'
    "i は行番号、s は原文断片、r は平仮名読み。"
)


def _coerce_json(text: str) -> dict:
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
        s = s.strip()
    if not s.startswith("{"):
        lo, hi = s.find("{"), s.rfind("}")
        if lo != -1 and hi > lo:
            s = s[lo:hi+1]
    return json.loads(s)


def _parse_response(text: str, lines: List[str]) -> Dict[int, Pairs]:
    obj = _coerce_json(text)
    raw = obj.get("lines")
    if not isinstance(raw, list):
        raise ValueError("missing 'lines' array")
    mapping: Dict[int, Pairs] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("i")
        if not isinstance(idx, int) or not (0 <= idx < len(lines)):
            continue
        tokens = entry.get("tokens") or []
        pairs: Pairs = []
        for t in tokens:
            if not isinstance(t, dict):
                continue
            s, r = t.get("s", ""), t.get("r", "")
            if isinstance(s, str) and isinstance(r, str) and s:
                pairs.append((s, r or s))
        # validate: surfaces concatenated == original line
        if "".join(s for s, _ in pairs) == lines[idx]:
            mapping[idx] = pairs
    return mapping


class LLMReadingClient:
    """OpenAI-compatible LLM 注音客户端。"""

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
        timeout: int = 300,
        max_retries: int = 2,
    ):
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def _endpoint(self) -> str:
        cached = getattr(self, "_endpoint_url_cache", None)
        if cached:
            return cached
        b = self.base_url
        url = b if b.endswith("/chat/completions") else b + "/chat/completions"
        self._endpoint_url_cache = url
        return url

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def annotate_lines(self, lines: List[str]) -> Tuple[Dict[int, Pairs], Optional[str]]:
        """一次请求注音整首歌词。返回 (mapping, error_or_None)。"""
        if not self.is_configured():
            return {}, "LLM not configured (set OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL)"

        numbered = "\n".join(f"{i}: {l}" for i, l in enumerate(lines))
        user_prompt = (
            "次の日本語の歌詞を行ごとに注音してください。\n"
            f"{_SCHEMA_HINT}\n歌詞：\n{numbered}"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "curl/7.88.1",
        }
        body: dict = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        # Try with json_object first, fall back without it
        optional_keys = ["response_format"]
        body_with_fmt = {**body, "response_format": {"type": "json_object"}}

        for attempt, req_body in enumerate([body_with_fmt, body]):
            try:
                raw = self._post(self._endpoint, headers, req_body)
                mapping = _parse_response(raw, lines)
                logger.info("[llm] annotated %d/%d lines", len(mapping), len(lines))
                return mapping, None
            except json.JSONDecodeError as e:
                if attempt == 0:
                    continue  # retry without json_object
                return {}, f"JSON parse error: {e}"
            except Exception as e:
                if attempt == 0 and "400" in str(e):
                    continue  # retry without response_format
                return {}, str(e)

        return {}, "all attempts failed"

    def _post(self, url: str, headers: dict, body: dict) -> str:
        import urllib.request as ur
        data = json.dumps(body).encode()
        req = ur.Request(url, data=data, headers=headers, method="POST")

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                with ur.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = json.loads(resp.read())
                choices = resp_data.get("choices") or []
                return choices[0]["message"]["content"]
            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break

        raise RuntimeError(f"LLM request failed: {last_err}")
