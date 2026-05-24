"""Novel Agent Web Portal Configuration"""
import os

# Project root
NOVEL_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DeepSeek API - 直接连接，不经过Hermes
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Portal settings
PORTAL_HOST = os.environ.get("PORTAL_HOST", "0.0.0.0")
PORTAL_PORT = int(os.environ.get("PORTAL_PORT", 8686))
DEBUG = os.environ.get("PORTAL_DEBUG", "1") == "1"
