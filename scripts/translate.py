#!/usr/bin/env python3
"""为英文标题的文章补充中文翻译标题 (titleCn)。

幂等：已有 titleCn、或标题本身是中文的，跳过。翻译在后端用 MiniMax 完成，
结果写回 docs/data/articles.json 的每篇文章的 titleCn 字段。
"""

import os
import re
import json
import time
import requests
from pathlib import Path

MINIMAX_API_URL = os.environ.get(
    "MINIMAX_API_URL", "https://api.minimaxi.com/anthropic/v1/messages"
)
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7")
ARTICLES_FILE = Path(__file__).parent.parent / "docs" / "data" / "articles.json"
CJK = re.compile(r"[一-鿿]")


def parse_minimax_content(result):
    """兼容 MiniMax extended thinking 的响应解析"""
    content = ""
    if "content" in result and isinstance(result["content"], list):
        for block in result["content"]:
            if isinstance(block, dict) and "text" in block:
                content = block["text"]
                break
            elif isinstance(block, str):
                content = block
                break
        if not content:
            for block in result["content"]:
                if isinstance(block, dict) and "thinking" in block:
                    content = block["thinking"]
                    break
    elif "choices" in result:
        content = result["choices"][0].get("message", {}).get("content", "")
    return content


def needs_translation(a):
    return not a.get("titleCn") and not CJK.search(a.get("title", ""))


def translate_batch(batch):
    """翻译一批标题，结果写回 batch 中各文章的 titleCn"""
    lines = [
        "把下列英文AI资讯标题翻译成简洁、准确、通顺的中文标题。",
        "保留专有名词与模型名的通用写法（如 GPT-5.6、Claude、Anthropic、OpenAI）。",
        "",
    ]
    for i, a in enumerate(batch):
        lines.append(f'{i + 1}. {a["title"]}')
    lines += [
        "",
        '只返回JSON数组，格式：[{"index":1,"cn":"中文标题"}, ...]，不要任何多余内容。',
    ]
    prompt = "\n".join(lines)

    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(
                MINIMAX_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": MINIMAX_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": MINIMAX_MODEL,
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120,
            )
            resp.raise_for_status()
            content = parse_minimax_content(resp.json())
            m = re.search(r"\[.*\]", content, re.DOTALL)
            if not m:
                raise ValueError("未匹配到JSON数组")
            arr = json.loads(m.group())
            for item in arr:
                idx = item.get("index", 0) - 1
                cn = (item.get("cn") or "").strip()
                if 0 <= idx < len(batch) and cn:
                    batch[idx]["titleCn"] = cn
            return
        except Exception as e:
            last_err = e
            print(f"   ↻ 第 {attempt + 1} 次失败: {e}")
            time.sleep(3)
    raise last_err


def main():
    if not MINIMAX_API_KEY:
        print("✗ 未设置 MINIMAX_API_KEY")
        return

    data = json.load(open(ARTICLES_FILE, encoding="utf-8"))
    pending = [a for a in data["articles"] if needs_translation(a)]
    print(f"待翻译 {len(pending)} 条")

    for i in range(0, len(pending), 10):
        batch = pending[i : i + 10]
        try:
            translate_batch(batch)
            print(f"  ✓ 批次 {i // 10 + 1} 完成")
        except Exception as e:
            print(f"  ✗ 批次 {i // 10 + 1} 失败: {e}")
        # 增量落盘：pending 里是 data 的引用，直接保存即可
        json.dump(
            data, open(ARTICLES_FILE, "w", encoding="utf-8"),
            ensure_ascii=False, indent=2,
        )
        time.sleep(1)

    print("✅ 完成")


if __name__ == "__main__":
    main()
