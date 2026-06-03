# Privacy Notice — demo-gen

## What demo-gen processes

demo-gen generates demo artifacts (HTML scripts and MP4 videos) from screenshots, screen recordings, and project documentation you supply.

## Data flows

### Default mode (local — recommended)

All processing runs on your machine:

- **Scripting**: Ollama with a locally-hosted model. No data leaves your machine.
- **Voice synthesis**: Kokoro ONNX or Piper TTS, running fully locally.
- **Video/image processing**: FFmpeg and Pillow, running fully locally.

### Cloud mode (`--cloud`)

When `--cloud` is passed, the scripting stage sends data to the Anthropic API:

- Content sent: text from any `--include-docs` files you explicitly list, plus step descriptions.
- Screenshots are **not** sent to the API; only the text context you specify.
- Anthropic may retain API inputs for safety review per their [usage policy](https://www.anthropic.com/legal/usage-policy).
- A consent prompt is displayed before any transmission listing the exact files to be sent.

## Your responsibilities

If screenshots or recordings contain personal data belonging to your users, you are responsible for ensuring you hold the legal basis to process that data and, in cloud mode, to transfer it to Anthropic. Use `--local` (default) to avoid any third-party transfer.

## Temporary files

All intermediate files (extracted frames, audio renders, subtitle files) are created in a session-scoped temporary directory and deleted automatically when the run completes, including on error.

## Model weights

Model weights are downloaded from Hugging Face over HTTPS and stored at `~/.demo-gen/models/`. SHA-256 checksums are verified against a pinned manifest before any model is loaded. The `~/.demo-gen/` directory is created with mode `0700`.

## Contact

Report privacy concerns via the project issue tracker.
