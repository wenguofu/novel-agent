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
