"""Unit tests for portal/token_utils.py (M3.1 W2 T2.7.1).

Targets line coverage 37% -> 80%+. Pure logic -- no DB, no Flask, no fixtures.
"""
from token_utils import count_tokens, truncate_to_tokens


# -- count_tokens -------------------------------------------------------

class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_none_input(self):
        # `if not text` covers both empty and None
        assert count_tokens(None) == 0

    def test_pure_chinese(self):
        # 4 Chinese chars x 1.5 = 6
        assert count_tokens("测试文本") == int(4 * 1.5)

    def test_pure_english(self):
        # 3 English words x 1.3 = 3.9 -> int = 3
        assert count_tokens("hello world test") == int(3 * 1.3)

    def test_mixed(self):
        # 4 Chinese + 2 English words (hello, world) =
        # 4*1.5 + 2*1.3 = 8.6 -> 8
        assert count_tokens(
            "测试 hello world 文本"
        ) == int(4 * 1.5 + 2 * 1.3)

    def test_punctuation_ignored(self):
        # Punctuation matches neither regex, contributes 0
        assert count_tokens("!!!") == 0

    def test_digits_ignored(self):
        # Digits match neither regex (English regex is [a-zA-Z]+ only)
        assert count_tokens("123 456") == 0

    def test_single_chinese_char(self):
        # 1 x 1.5 = 1.5 -> 1
        assert count_tokens("中") == int(1.5)

    def test_single_english_word(self):
        # 1 word x 1.3 = 1.3 -> 1
        assert count_tokens("hello") == int(1.3)

    def test_mixed_chinese_punctuation(self):
        # 2 Chinese (3.0) + 3 punctuation (0) = 3
        assert count_tokens("测试!!!") == int(2 * 1.5)

    def test_chinese_char_range_edge_low(self):
        # First char in CJK Unified Ideographs range
        assert count_tokens("一") == int(1.5)

    def test_chinese_char_range_edge_high(self):
        # Last char in CJK Unified Ideographs range (鿿 = U+9FFF)
        assert count_tokens("鿿") == int(1.5)


# -- truncate_to_tokens -------------------------------------------------

class TestTruncateToTokens:
    def test_empty_string(self):
        assert truncate_to_tokens("", 100) == ""

    def test_none_input(self):
        assert truncate_to_tokens(None, 100) == ""

    def test_short_text_no_truncation(self):
        text = "测试"
        result = truncate_to_tokens(text, 100)
        assert result == text

    def test_exact_fit(self):
        # 2 Chinese chars = 3 tokens. max_tokens=3 should fit both.
        text = "测试"
        result = truncate_to_tokens(text, 3)
        assert result == text

    def test_truncates_chinese(self):
        # 4 Chinese chars = 6 tokens. max_tokens=3 should fit 2.
        text = "一二三四"
        result = truncate_to_tokens(text, 3)
        assert result == "一二"

    def test_truncates_english(self):
        # "hello" = 5 English chars, each 1.3 token. With max=2, 1 char fits.
        text = "hello"
        result = truncate_to_tokens(text, 2)
        assert result == "h"

    def test_truncates_mixed(self):
        # Mix of Chinese and English
        text = "测试hello世界"
        result = truncate_to_tokens(text, 5)
        # "测"=1.5, "试"=1.5, "h"=1.3 -> 4.3; next "e"=1.3 would be 5.6 > 5
        assert result == "测试h"

    def test_punctuation_uses_05_token(self):
        # Punctuation = 0.5 tokens each
        text = "!!!"
        result = truncate_to_tokens(text, 1.0)
        # First 2 punctuation marks = 1.0 token; 3rd would be 1.5 > 1.0
        assert result == "!!"

    def test_zero_max_tokens(self):
        # max_tokens=0 -> nothing fits
        assert truncate_to_tokens("测试", 0) == ""

    def test_max_tokens_smaller_than_char(self):
        # max_tokens=1 -> Chinese (1.5) doesn't fit, punctuation (0.5) does
        text = "!测"
        result = truncate_to_tokens(text, 1)
        # "!"=0.5 fits; then "测"=1.5 would push total to 2.0 > 1
        assert result == "!"

    def test_chinese_at_range_edge(self):
        # Char at end of CJK range should be treated as Chinese (1.5)
        text = "鿿"
        result = truncate_to_tokens(text, 1.5)
        assert result == "鿿"

    def test_uppercase_english(self):
        # isalpha() is True for uppercase too -> 1.3 tokens
        text = "ABCDE"
        result = truncate_to_tokens(text, 2)
        # 'A' (1.3) + 'B' (1.3) = 2.6 > 2, so just 'A'
        assert result == "A"

    def test_digits_get_05_token(self):
        # isalpha() is False for digits -> 0.5 tokens
        text = "123"
        result = truncate_to_tokens(text, 1.0)
        # '1'(0.5) + '2'(0.5) = 1.0; '3' would be 1.5 > 1.0
        assert result == "12"
