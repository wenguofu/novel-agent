"""Test the check_tdd_compliance.sh script via subprocess + a temp git repo."""
import os
import subprocess
from pathlib import Path

import pytest


def _init_tmp_repo(tmp_path: Path) -> Path:
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in [
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
        ["git", "commit", "--allow-empty", "-m", "init"],
    ]:
        subprocess.run(cmd, cwd=tmp_path, env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return tmp_path


SCRIPT = Path(__file__).parent.parent / "scripts" / "check_tdd_compliance.sh"


def test_blocks_portal_change_without_test(tmp_path):
    """portal/ change without tests/ should be blocked."""
    repo = _init_tmp_repo(tmp_path)
    (repo / "portal").mkdir()
    (repo / "portal" / "app.py").write_text("# changed\n")
    subprocess.run(["git", "add", "portal/app.py"], cwd=repo, check=True)
    result = subprocess.run(["bash", str(SCRIPT)], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0, f"Expected block, got: {result.stdout}\n{result.stderr}"


def test_allows_portal_change_with_test(tmp_path):
    """portal/ change with matching tests/ change should be allowed."""
    repo = _init_tmp_repo(tmp_path)
    (repo / "portal").mkdir()
    (repo / "tests").mkdir()
    (repo / "portal" / "app.py").write_text("# changed\n")
    (repo / "tests" / "test_app.py").write_text("# test added\n")
    subprocess.run(["git", "add", "portal/app.py", "tests/test_app.py"], cwd=repo, check=True)
    result = subprocess.run(["bash", str(SCRIPT)], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, f"Expected allow, got: {result.stdout}\n{result.stderr}"


def test_allows_hotfix_commits(tmp_path):
    """Commit message containing 'hotfix' should bypass the gate."""
    repo = _init_tmp_repo(tmp_path)
    (repo / "portal").mkdir()
    (repo / "portal" / "app.py").write_text("# hotfix\n")
    subprocess.run(["git", "add", "portal/app.py"], cwd=repo, check=True)
    # Commit-msg path via env var HOOK_COMMIT_MSG_FILE
    msg_file = repo / "COMMIT_EDITMSG"
    msg_file.write_text("hotfix: emergency fix\n")
    result = subprocess.run(
        ["bash", "-c", f"HOOK_COMMIT_MSG_FILE={msg_file} bash {SCRIPT}"],
        cwd=repo, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"hotfix should bypass, got: {result.stdout}\n{result.stderr}"
