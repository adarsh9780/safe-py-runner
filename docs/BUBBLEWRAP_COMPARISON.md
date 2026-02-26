# Bubblewrap vs safe-py-runner

This guide compares Linux `bubblewrap` (`bwrap`) with `safe-py-runner` for the same practical goal:
running Python code with guardrails such as import controls, memory limits, and timeouts.

## Quick Comparison

| Capability | `safe-py-runner` | `bubblewrap` (`bwrap`) |
| --- | --- | --- |
| Python import controls | Built in (`allow` / `restrict` policy lists) | Not built in; you enforce at OS/filesystem boundary, not Python symbol level |
| Python builtin controls | Built in (`allowed_builtins` / `blocked_builtins`) | Not built in |
| Timeout | Built in via subprocess timeout | Not built in; use an external timeout wrapper/supervisor |
| Memory limit | Built in via `RLIMIT_AS` on POSIX (platform caveats apply) | Not built in by itself; usually paired with cgroups/ulimit tooling |
| OS isolation boundary | Process-level guardrails, not full OS sandbox | Strong Linux namespace-based isolation (when configured correctly) |
| Platform support | Python environments (memory enforcement behavior varies by OS) | Linux-focused |
| Setup complexity | Low | Medium to high |

## What This Means In Practice

`safe-py-runner` is better when:
- You want Python-level controls quickly (import/builtin/global policy).
- You need a lightweight integration in agent workflows.
- You want one library call for execution plus result capture.

`bubblewrap` is better when:
- You need stronger OS-level isolation on Linux.
- You run untrusted multi-tenant workloads.
- You can invest in sandbox setup and operational hardening.

## Recommended Usage

- For internal tools and controlled agent workloads, `safe-py-runner` can be enough.
- For hostile or public-user code in production, prefer Linux sandboxing (for example `bubblewrap`, containers, or VM boundaries) as the primary isolation layer.
- You can combine both: put Python execution inside an OS sandbox and still use `safe-py-runner` for Python-level policy and structured I/O.
