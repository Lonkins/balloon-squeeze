# Security Policy

Balloon Squeeze is a research instrument. Its default (`mock`) path is fully offline and handles
no secrets. Real-provider runs read an API key from a local, git-ignored `.env` (documented in
`.env.example`); no key or secret is ever committed to the repository.

## Reporting a vulnerability

Please report suspected vulnerabilities — or any accidental secret exposure — **privately**, via a
GitHub [security advisory](https://github.com/Lonkins/balloon-squeeze/security/advisories/new),
rather than opening a public issue.

**Never** paste an API key, token, or other secret into a public issue or pull request. If a
secret is ever exposed, rotate it immediately and report it through the advisory flow.
