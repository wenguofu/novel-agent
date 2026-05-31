"""Novel Agent Web Portal Configuration"""
import os

# Project root
NOVEL_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# MiniMax M2.7 API (Anthropic-compatible endpoint)
# Also reads legacy DEEPSEEK_* env vars as fallback
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
MINIMAX_API_BASE = os.environ.get("MINIMAX_API_BASE", os.environ.get("DEEPSEEK_API_BASE", "https://api.minimaxi.com/anthropic"))
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", os.environ.get("DEEPSEEK_MODEL", "MiniMax-M2.7"))

# Legacy aliases for backward compatibility with code that uses DEEPSEEK_* names
DEEPSEEK_API_KEY = MINIMAX_API_KEY
DEEPSEEK_API_BASE = MINIMAX_API_BASE
DEEPSEEK_MODEL = MINIMAX_MODEL

# Default generation params (overridden by portal settings)
DEFAULT_TEMPERATURE = float(os.environ.get("MINIMAX_TEMPERATURE", os.environ.get("DEEPSEEK_TEMPERATURE", "0.7")))
DEFAULT_MAX_TOKENS = int(os.environ.get("MINIMAX_MAX_TOKENS", os.environ.get("DEEPSEEK_MAX_TOKENS", "8192")))
DEFAULT_TOP_P = float(os.environ.get("MINIMAX_TOP_P", os.environ.get("DEEPSEEK_TOP_P", "0.9")))

# Portal settings
PORTAL_HOST = os.environ.get("PORTAL_HOST", "0.0.0.0")
PORTAL_PORT = int(os.environ.get("PORTAL_PORT", 35001))
DEBUG = os.environ.get("PORTAL_DEBUG", "1") == "1"
