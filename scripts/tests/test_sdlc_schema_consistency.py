import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "check_sdlc_schema_consistency.py"
)
_spec = importlib.util.spec_from_file_location(
    "check_sdlc_schema_consistency", _MODULE_PATH
)
checker = importlib.util.module_from_spec(_spec)
sys.modules["check_sdlc_schema_consistency"] = checker
_spec.loader.exec_module(checker)

check_consistency = checker.check_consistency

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_check_consistency_passes_against_current_repo_state():
    errors = check_consistency(_REPO_ROOT)

    assert errors == []


def test_check_consistency_reports_divergent_file_by_name(tmp_path):
    scratch = tmp_path
    (scratch / "agents").mkdir()
    (scratch / "skills" / "sdlc").mkdir(parents=True)
    (scratch / "docs" / "features").mkdir(parents=True)

    good_finding_schema = """```json
{
  "agent": "sdlc-style-reviewer",
  "findings": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "summary": "<wenyan-ultra compressed>",
      "failure_scenario": "<wenyan-ultra compressed>"
    }
  ]
}
```"""
    divergent_finding_schema = """```json
{
  "agent": "sdlc-code-reviewer",
  "findings": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "summary": "<wenyan-ultra compressed>",
      "failure_scenario": "<wenyan-ultra compressed>",
      "extra_field": "should not be here"
    }
  ]
}
```"""

    (scratch / "agents" / "sdlc-style-reviewer.md").write_text(good_finding_schema)
    (scratch / "agents" / "sdlc-code-reviewer.md").write_text(divergent_finding_schema)

    errors = checker.check_consistency(
        scratch,
        source_files=[
            Path("agents/sdlc-style-reviewer.md"),
            Path("agents/sdlc-code-reviewer.md"),
        ],
    )

    assert len(errors) == 1
    assert "agents/sdlc-code-reviewer.md" in errors[0]
