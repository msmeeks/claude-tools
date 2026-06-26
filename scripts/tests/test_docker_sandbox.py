import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "run-next-plan.py"
_spec = importlib.util.spec_from_file_location("run_next_plan", _MODULE_PATH)
run_next_plan = importlib.util.module_from_spec(_spec)
sys.modules["run_next_plan"] = run_next_plan
_spec.loader.exec_module(run_next_plan)

get_image_tag = run_next_plan.get_image_tag
build_run_command = run_next_plan.build_run_command


def test_get_image_tag_sanitizes_slug():
    assert get_image_tag("msmeeks/claude-tools") == "ralph-msmeeks-claude-tools:latest"


def test_build_run_command_returns_bare_argv_when_no_dockerfile(tmp_path):
    claude_argv = ["claude", "-p", "-"]
    with patch("subprocess.run") as mock_run:
        result = build_run_command(
            repo_root=tmp_path,
            dockerfile=tmp_path / "meta" / "ralph.dockerfile",
            env={},
            claude_argv=claude_argv,
        )
    assert result == claude_argv
    mock_run.assert_not_called()


def _make_dockerfile(tmp_path):
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    dockerfile = meta_dir / "ralph.dockerfile"
    dockerfile.write_text("FROM scratch\n")
    return dockerfile


def _no_existing_image(*args, **kwargs):
    if args[0][:2] == ["docker", "inspect"]:
        return type("R", (), {"returncode": 1, "stdout": ""})()
    return type("R", (), {"returncode": 0, "stdout": ""})()


def test_build_run_command_builds_image_and_returns_docker_run_argv(tmp_path):
    dockerfile = _make_dockerfile(tmp_path)
    claude_argv = ["claude", "-p", "-"]
    with patch("subprocess.run", side_effect=_no_existing_image) as mock_run:
        result = build_run_command(
            repo_root=tmp_path,
            dockerfile=dockerfile,
            env={"repo_slug": "me/repo"},
            claude_argv=claude_argv,
        )

    build_calls = [c for c in mock_run.call_args_list if c.args[0][1] == "build"]
    assert len(build_calls) == 1

    assert result[:2] == ["docker", "run"]
    assert "-v" in result
    assert f"{tmp_path.resolve()}:/workspace" in result
    assert "-w" in result
    assert "/workspace" in result
    assert result.count("-e") == 4
    assert "ANTHROPIC_API_KEY" in result
    assert "GITHUB_TOKEN" in result
    assert "=" not in "".join(result)
    assert result[-len(claude_argv):] == claude_argv


def test_build_run_command_dies_on_symlinked_dockerfile(tmp_path):
    real = tmp_path / "real.dockerfile"
    real.write_text("FROM scratch\n")
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    link = meta_dir / "ralph.dockerfile"
    link.symlink_to(real)
    with patch("subprocess.run") as mock_run, pytest.raises(SystemExit):
        build_run_command(
            repo_root=tmp_path, dockerfile=link, env={}, claude_argv=["claude"]
        )
    mock_run.assert_not_called()


def test_build_run_command_dies_on_dockerfile_outside_repo_root(tmp_path):
    outside_dir = tmp_path.parent / "outside_dockerfile_dir"
    outside_dir.mkdir(exist_ok=True)
    outside_dockerfile = outside_dir / "ralph.dockerfile"
    outside_dockerfile.write_text("FROM scratch\n")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    with patch("subprocess.run") as mock_run, pytest.raises(SystemExit):
        build_run_command(
            repo_root=repo_root, dockerfile=outside_dockerfile, env={}, claude_argv=["claude"]
        )
    mock_run.assert_not_called()
    outside_dockerfile.unlink()
    outside_dir.rmdir()


def test_build_run_command_skips_rebuild_when_image_newer_than_dockerfile(tmp_path):
    dockerfile = _make_dockerfile(tmp_path)

    def _fresh_image(*args, **kwargs):
        if args[0][:2] == ["docker", "inspect"]:
            return type("R", (), {"returncode": 0, "stdout": "2099-01-01T00:00:00Z"})()
        return type("R", (), {"returncode": 0, "stdout": ""})()

    with patch("subprocess.run", side_effect=_fresh_image) as mock_run:
        build_run_command(
            repo_root=tmp_path, dockerfile=dockerfile, env={}, claude_argv=["claude"]
        )

    build_calls = [c for c in mock_run.call_args_list if c.args[0][1] == "build"]
    assert len(build_calls) == 0


def test_build_run_command_skip_build_makes_no_subprocess_calls(tmp_path):
    dockerfile = _make_dockerfile(tmp_path)
    with patch("subprocess.run") as mock_run:
        result = build_run_command(
            repo_root=tmp_path,
            dockerfile=dockerfile,
            env={},
            claude_argv=["claude"],
            skip_build=True,
        )
    mock_run.assert_not_called()
    assert result[:2] == ["docker", "run"]


def test_get_image_tag_has_no_slash_or_invalid_chars():
    tag = get_image_tag("Org/Repo Name!@#")
    assert "/" not in tag
    assert " " not in tag
    assert tag.startswith("ralph-")
    assert tag.endswith(":latest")
