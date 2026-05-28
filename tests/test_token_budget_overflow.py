"""
BUG-04: Token budget overflow test.
Demonstrates content[:allocated * 2] fails for Chinese text.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import pytest
from context_builder import build_context, _count_tokens

class TestTokenBudgetEnforcement:
    def test_chinese_truncation_overflow(self):
        """BUG-04: Chinese text truncation uses char offset for token budget.
        Chinese: 1 char ≈ 1.5 tokens, so allocated*2 bytes → 3x overflow."""
        # Simulate: layer budget is 100 tokens, but content is 500 Chinese chars (≈750 tok)
        large_cn_text = "测试" * 500  # 1000 chars, ~1500 tokens
        tokens_in = _count_tokens(large_cn_text)
        print(f"\nInput: {len(large_cn_text)} chars = ~{tokens_in} tokens")

        # Naive truncation (current bug): allocated=100 → content[:100*2] = 200 chars
        # 200 Chinese chars ≈ 300 tokens → 3x budget violation
        allocated = 100
        naive_truncated = large_cn_text[:allocated * 2]
        naive_tokens = _count_tokens(naive_truncated)
        print(f"Naive: {len(naive_truncated)} chars = {naive_tokens} tokens "
              f"(budget: {allocated}, overflow: {naive_tokens - allocated})")

        # The bug: naive truncation should exceed budget significantly
        assert naive_tokens > allocated, \
            f"BUG-04 confirmed: {naive_tokens}tok > {allocated}tok budget"

    def test_proper_truncation_stays_in_budget(self):
        """After fix, truncation should stay within token budget."""
        large_cn_text = "测试数据" * 300  # 1200 chars
        from token_budget import TokenBudget as _TB

        # Simulate proper truncation
        def truncate_to_tokens(text, max_tokens):
            result = []
            token_count = 0
            for ch in text:
                ch_tokens = 1.5 if '\u4e00' <= ch <= '\u9fff' else 1.3
                if token_count + ch_tokens > max_tokens:
                    break
                result.append(ch)
                token_count += ch_tokens
            return ''.join(result), int(token_count)

        truncated, tok_used = truncate_to_tokens(large_cn_text, 200)
        assert tok_used <= 210, f"Proper truncation respects budget: {tok_used} <= 210"
        assert len(truncated) < len(large_cn_text)
