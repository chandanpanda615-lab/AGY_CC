---
name: batch-mark
description: Automatically scans the workspace for unmarked CA Inter student copies and dispatches parallel ca_evaluator subagents to grade them concurrently.
---

# Batch Mark Copies

This skill coordinates the evaluation of multiple student copies concurrently by spawning independent subagents for each unmarked copy.

## Execution Steps

1. **Scan Directories**: Use `list_dir` or a python script to find all student folders inside any series folder (i.e. any subfolder inside a root directory folder).
2. **Filter Unmarked**: Check if the student folder contains a file ending with `_evaluated.pdf`. If it does NOT, the copy is considered "unmarked".
3. **Dispatch Subagents**: For every unmarked folder found, invoke a single `ca_evaluator` subagent.
   - Provide the prompt: `"Evaluate the copy in folder: <SeriesName>/<StudentName>"`
   - Use the tool `invoke_subagent` and launch them concurrently in an array.
4. **Wait and Monitor**: You do not need to poll. The system will automatically wake you up when a subagent finishes or sends a message. You can report the final status of the batch once all subagents complete.
