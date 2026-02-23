# Agent Protocol

## Commit & Testing Procedures

1. Always update the `commit_message` file in the root directory whenever a change is made.
2. Overwrite the file if the previous git commit message doesn't match the current content of the `commit_message`; otherwise, append the new changes.
3. For every bug and feature we add or report, create a dedicated test case to prevent regressions.

## Environment & Communication

1. Use `uv` as the default package manager, falling back to `python3` or `python` if necessary.
2. If a requested change seems suboptimal, point it out and provide a rationale.
3. Always explain technical points in layman's terms with clear examples.

## Bug And Feature Request

1. Understand the bug or feature request thoroughly, instead of making assumptions, ask questions or look through the code for more context.
2. Explain the issue or feature request in your own words and ask for confirmation.
3. In case of a bug, first explain why it happened and what are the possible solutions. Don't be lazy, please explain it simple terms.
