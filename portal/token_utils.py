"""
Token Utilities — shared token counting and truncation logic.
Used by context_builder, rag_engine, and portal app.
"""

import re


def count_tokens(text):
    """Estimate token count: Chinese chars ≈ 1.5 tokens, English words ≈ 1.3 tokens."""
    if not text:
        return 0
    cn = len(re.findall(r'[一-鿿]', text))
    en = len(re.findall(r'[a-zA-Z]+', text))
    return int(cn * 1.5 + en * 1.3)


def truncate_to_tokens(text, max_tokens):
    """Truncate text to fit within max_tokens using character-level counting.
    Accurate for Chinese text — uses character iteration, not byte slicing."""
    if not text:
        return ""
    result = []
    token_count = 0
    for ch in text:
        ch_tokens = 1.5 if '一' <= ch <= '鿿' else 1.3 if ch.isalpha() else 0.5
        if token_count + ch_tokens > max_tokens:
            break
        result.append(ch)
        token_count += ch_tokens
    return ''.join(result)
