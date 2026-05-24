"""Novel Agent Web Portal Configuration"""
import os

# Project root
NOVEL_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DeepSeek API - 直接连接，不经过Hermes
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Default generation params (overridden by portal settings)
DEFAULT_TEMPERATURE = float(os.environ.get("DEEPSEEK_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.environ.get("DEEPSEEK_MAX_TOKENS", "8192"))
DEFAULT_TOP_P = float(os.environ.get("DEEPSEEK_TOP_P", "0.9"))

# Portal settings
PORTAL_HOST = os.environ.get("PORTAL_HOST", "0.0.0.0")
PORTAL_PORT = int(os.environ.get("PORTAL_PORT", 35001))
DEBUG = os.environ.get("PORTAL_DEBUG", "1") == "1"
