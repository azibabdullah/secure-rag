# Security policy

SecureRAG is a security tool, so reports of weaknesses are especially welcome.

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | ✅ |
| < 1.0 | ❌ |

## Reporting a vulnerability

Please report privately through GitHub: open the **Security** tab of this repository and choose **Report a vulnerability**. Do not open a public issue.

Include what you did, what happened, and if possible a minimal file or prompt that reproduces it. You can expect a first reply within 7 days.

## In scope

- Prompt-injection inputs (messages or documents) that reach the language model despite PromptGuard or DocumentGuard
- Hidden document content that is not inspected
- Bypasses of encryption, integrity checks or the locked-down interface
- Leaks of documents or conversations outside `%LOCALAPPDATA%\SecureRAG`

## Out of scope

Known limitations listed in the README (for example, authority-style instructions in visible page text) and false positives. Please report those as normal issues instead.
