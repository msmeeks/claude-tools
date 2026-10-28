"""Shared stand-ins for the orchestration tests."""
import json


class _FakePopen:
    """Stands in for the plan session: records the prompt, marks the plan done, exits 0."""

    def __init__(self, prompts, prd_path, *args, **kwargs):
        self._prompts = prompts
        self._prd_path = prd_path
        self.returncode = 0
        self.stdin = self
        self.stdout = iter(["<plan>only-plan.md</plan>\n", "<promise>COMPLETE</promise>\n"])

    def write(self, text):
        self._prompts.append(text)

    def close(self):
        data = json.loads(self._prd_path.read_text())
        for entry in data["plans"]:
            entry["status"] = "done"
        self._prd_path.write_text(json.dumps(data))

    def wait(self):
        return 0
