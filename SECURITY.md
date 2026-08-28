# SECURITY.md — Portable USB LLM Agent

## Threat model

This project runs a local LLM that can write files and execute a limited
set of developer commands on your machine, driven by natural-language
task descriptions. The primary risks this design defends against:

1. **The model itself is not trustworthy input.** Even a well-behaved
   model can hallucinate destructive or out-of-scope actions. A
   maliciously crafted task, or content the model reads from a file that
   contains embedded instructions ("prompt injection"), could try to
   direct the model toward path traversal, command injection, or
   escaping the intended workspace.
2. **The user is trusted, but the request surface should still fail
   closed.** Path validation, command allowlisting, and permission
   flags (`allow_commands`, `allow_overwrite`) exist so that even a
   correctly-behaving-but-careless request can't accidentally touch
   files outside `workspace/`.
3. **Local network exposure.** Both the model server and the agent API
   bind to `127.0.0.1` only. Nothing in this project is designed to be
   reachable from other devices on your network. Do not change the
   `--host` flags to `0.0.0.0` — doing so would expose an unauthenticated
   code-execution-adjacent API to your entire local network.

## What is intentionally blocked

- **All file operations are contained to `workspace/`.** Absolute paths,
  `..` traversal, Windows drive letters (`C:\`), UNC paths (`\\server\`),
  drive-relative paths (`C:foo`), and Windows reserved device names
  (`CON`, `PRN`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`) are all rejected.
  Symlinks that resolve outside `workspace/` are also rejected (checked
  after resolution, not before).
- **ZIP artifact creation is contained to `artifacts/`.** Artifact names
  are parsed with Windows path semantics regardless of host OS, so
  backslash-based traversal attempts (`..\..\evil`) are caught the same
  way forward-slash attempts are.
- **Command execution is allowlisted, not blacklisted-by-exception.**
  Only `python`, `pytest`, `npm`, `node`, and `git` may run. Everything
  else is rejected by default — including but not limited to
  PowerShell, `cmd`, `bash`/`sh`, `curl`/`wget`, `ssh`/`scp`, `rm`/`del`,
  `format`, `shutdown`, registry tools, and package managers that modify
  system state (`choco`, `winget`, `scoop`).
- **Commands never run through a shell.** `subprocess.run(..., shell=False)`
  is used unconditionally — there is no shell metacharacter expansion,
  so `&&`, `|`, backticks, etc. in a command argument do not chain
  additional commands.
- **Commands require explicit opt-in.** `run_command` refuses to execute
  unless the API request includes `"allow_commands": true`. This is not
  a value the model can set for itself — it's read from the original
  caller's request only.
- **Overwriting existing files requires explicit opt-in.** `write_file`
  refuses to overwrite an existing file unless the request includes
  `"allow_overwrite": true`.
- **Deletion is permanently unavailable.** There is no delete tool wired
  into the agent. If a generated file needs to go, remove it yourself
  after reviewing what's in `workspace/`.
- **Command output and file sizes are capped** to prevent a single
  runaway command or file from consuming excessive memory or flooding
  logs.
- **Logs never contain prompts, file contents, or command output.** Only
  metadata (which tool ran, success/failure, counts) is logged.

## Explicit limitations — read before trusting this project with anything sensitive

- **Command execution is dangerous even with an allowlist.** `python`,
  `npm`, and `git` are all capable of running arbitrary code themselves
  (`python -c "..."`, npm postinstall scripts, git hooks). The allowlist
  restricts *which binary* runs, not *what that binary is capable of*.
  Treat `allow_commands: true` as "let the agent run code on this
  machine," not as a sandboxed-execution guarantee. This project does
  not implement a sandbox, container, or VM boundary.
- **Generated code must be reviewed before you run it outside this
  project's own constrained `run_command`, and before you trust it in
  any other context.** The agent's containment applies to *its own*
  actions during a session — it does nothing to make code it generates
  safe to run elsewhere later.
- **Dependency installation is not automatic and should stay that way.**
  If a task would benefit from `pip install` or `npm install`, that is a
  `run_command` call like any other — it still requires
  `allow_commands: true`, and you should look at what's being installed
  before approving tasks that do this routinely. This project does not
  maintain its own allowlist of "safe" packages.
- **This is a single-user, single-machine, loopback-only design.** There
  is no authentication on the agent API beyond "can reach 127.0.0.1 on
  this machine." Do not port-forward, tunnel, or otherwise expose either
  server's port to a network you don't fully trust.
- **The model can still be wrong.** Passing every containment check does
  not mean the *content* the model writes is correct, secure, or free of
  its own vulnerabilities (e.g. it could write Python with SQL injection
  in it). This project constrains *where* the agent can act, not the
  quality of what it produces.

## How to safely use the workspace

- Treat `workspace/` as disposable, reviewable scratch space — not a
  place to point at an existing project you care about without a backup.
- Start tasks with `allow_commands: false` (the default) unless you
  specifically need tests/builds to run, and read the task's plan/diff
  before re-running with commands allowed.
- Periodically clear out `workspace/` manually (deletion is intentionally
  not exposed to the agent) rather than letting old generated projects
  accumulate.
- Review `artifacts/*.zip` contents before sharing them elsewhere — the
  agent packages what it wrote, not what you've manually verified.
- If you ever see `run_command` being asked to run something you don't
  recognize or didn't expect from your task description, treat that as
  a signal to stop and inspect the conversation trace (`/agent` response
  includes a full `trace` field), not just to approve it.