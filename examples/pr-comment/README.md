# PR comment demo

This example intentionally lists a known malicious npm package in a lockfile:

- `47cliens_server@0.0.1-security`
- OSV: `MAL-2022-30`

No package code is downloaded or executed. The PR workflow only parses the
lockfile and looks up the package in a local demonstration risk index.
