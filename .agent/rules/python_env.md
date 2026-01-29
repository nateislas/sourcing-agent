---
description: Rule to ensure the Python virtual environment is activated before execution.
globs: ["**/*.py"]
alwaysApply: true
---

# Python Environment Activation Rule

Always ensure that the Python virtual environment is activated before executing any Python-related commands. This ensures that the correct dependencies and Python version are used.

- **Environment Directory**: `env/` (located in the project root)
- **Activation Command**: `source env/bin/activate`

## Guidelines for Execution

When running any Python command (e.g., `python`, `pip`, `pytest`, `ruff`), you MUST either:
1.  **Activate the environment first** in the same command string:
    ```bash
    source env/bin/activate && python path/to/script.py
    ```
2.  **Use the absolute path** to the executable within the virtual environment:
    ```bash
    ./env/bin/python path/to/script.py
    ```

## Preferred Usage
Prefer the `source env/bin/activate && ...` pattern for clarity and consistency across different shell environments.
