"""Fixture for AST scanner tests. NOT a real Flask app — function bodies are inert."""
from flask import Flask

app = Flask(__name__)

@app.route("/")
def root():
    """Root index — serves the SPA shell."""
    return "<html></html>"

@app.route("/api/novels", methods=["GET", "POST"])
def api_novels():
    """List or create novels."""
    return []

@app.route("/api/novels/<name>")
def api_novel(name):
    """Get one novel by name."""
    return {}

@app.route("/api/novels/<name>/chapters/<path:ref>", methods=["DELETE"])
def api_delete_chapter(name, ref):
    """Delete a chapter."""
    return {}

@app.route("/api/static/<path:filename>")
def static_files(filename):
    """Serve static assets."""
    return ""

@app.route("/api/characters/<name>/<int:cid>", methods=["PUT", "DELETE"])
def api_character_ops(name, cid):
    """Update or delete one character."""
    return {}

@app.route("/api/crud/<int:row_id>", methods=["GET", "POST", "PUT", "DELETE"])
def api_crud(row_id):
    """Generic CRUD endpoint with all four methods."""
    return {}

async def _helper():  # unrelated async; should be ignored
    return None

@app.route("/api/async/<name>")
async def api_async(name):
    """Async endpoint — exercises AsyncFunctionDef branch."""
    return {}
