---
description: Rule for ensuring project documentation and artifacts are synced to .cursor/docs
globs: .gemini/antigravity/brain/**/*
---
# Documentation Sync

Every time an artifact or document is created in the brain directory (e.g., in `.gemini/antigravity/brain/`), it MUST also be synced to `.cursor/docs/` in the workspace root to ensure visibility for the user.

- Always check `.cursor/docs` for the latest implementation plans, walkthroughs, and task lists.
- When creating new artifacts, immediately copy them to `.cursor/docs/`.
