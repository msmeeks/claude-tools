# LLM Context Index

Load this file first. Then load only the specific doc files relevant to your task.

## Project docs
- [overview.md](overview.md) — project purpose, users, architecture, and repo layout
- [features/agents.md](features/agents.md) — subagent definitions in agents/ and how to use them
- [features/skills.md](features/skills.md) — slash-command skills in skills/ and how each works
- [features/setup.md](features/setup.md) — bootstrap scripts: setup-symlinks.sh (CLI) and setup-symlinks-desktop.sh (macOS Desktop app)
- [features/third-party-skills.md](features/third-party-skills.md) — Matt Pocock's engineering skills: install, per-project setup, skill list, and local mods
- [features/custom-llm.md](features/custom-llm.md) — route Claude Code to Ollama, Gemini, or OpenAI via claude-code-router proxy
- [features/demo-gen.md](features/demo-gen.md) — Python CLI that generates HTML + MP4 demo artifacts; invoked by the `/demo` skill
- [features/run-next-plan.md](features/run-next-plan.md) — Ralph Wiggum loop: non-interactive orchestrator that drives meta/plans/ to completion, including the SDLC review gate
- [features/sdlc-review-handoff.md](features/sdlc-review-handoff.md) — compressed file-based handoff between /sdlc orchestrator and all 8 Phase 3/4 review+QA agents

## Dev
- [../README.md](../README.md) — quick-start, skills reference, agents reference
