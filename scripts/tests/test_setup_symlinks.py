"""`setup-symlinks.sh`: links the repo's installable files into `~/.claude/`.

Runs the real script with `HOME` pointed at a temp dir, so it links the live repo tree.
"""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_SCRIPT = REPO / "setup-symlinks.sh"


def _run(home):
    return subprocess.run(
        ["bash", str(_SCRIPT)],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
        capture_output=True,
        text=True,
        check=True,
    )


def _linked(home, area):
    return sorted(p.name for p in (home / ".claude" / area).iterdir() if p.is_symlink())


def test_links_every_agent_but_not_the_area_doc(tmp_path):
    _run(tmp_path)
    expected = sorted(p.name for p in (REPO / "agents").glob("*.md") if p.name != "CONTEXT.md")
    assert _linked(tmp_path, "agents") == expected


def test_links_only_executable_scripts(tmp_path):
    _run(tmp_path)
    expected = sorted(
        p.name
        for p in (REPO / "scripts").iterdir()
        if p.is_file() and p.stat().st_mode & 0o111
    )
    assert expected, "repo should ship at least one executable script"
    assert _linked(tmp_path, "scripts") == expected


def test_prunes_stray_links_from_earlier_runs(tmp_path):
    for area, name in [("agents", "CONTEXT.md"), ("scripts", "pyproject.toml")]:
        (tmp_path / ".claude" / area).mkdir(parents=True, exist_ok=True)
        (tmp_path / ".claude" / area / name).symlink_to(REPO / area / name)

    out = _run(tmp_path).stdout

    assert not (tmp_path / ".claude" / "agents" / "CONTEXT.md").is_symlink()
    assert not (tmp_path / ".claude" / "scripts" / "pyproject.toml").is_symlink()
    assert out.count("  unlink ") == 2


def test_leaves_links_it_does_not_own(tmp_path):
    elsewhere = tmp_path / "elsewhere.md"
    elsewhere.write_text("not ours")
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "third-party.md").symlink_to(elsewhere)

    _run(tmp_path)

    assert (agents / "third-party.md").is_symlink()


def test_rerun_is_a_no_op(tmp_path):
    _run(tmp_path)
    actions = {line.split()[0] for line in _run(tmp_path).stdout.splitlines() if line[:2] == "  "}
    assert actions == {"skip"}
