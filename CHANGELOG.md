# Changelog

All notable changes to SecureRAG are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-13

### Added
- New brand: striped SecureRAG logo, purple theme and app icon.
- Animated start-up while the security models load, and a welcome screen with a setup guide.
- Glossy dashboard with an optional glowing logo backdrop.
- Screening summary tables and charts on Overview, Documents and in screening reports.

### Changed
- Setup guide opens as a side sheet; smoother sidebar collapse on narrow windows.

## [0.4.0] - 2026-11-12

### Added
- Two security models: PromptGuard (`FINAL`) for messages and DocumentGuard (`v3 seed 2`) for documents.
- Full document inspection: metadata, annotations, comments, form fields, attachments, tracked changes and invisible text. A malicious hidden part blocks the whole file.
- Documents mode answers across selected files and explains every withheld passage.
- Security inspector, command palette (`Ctrl+K`) and welcome screen.

## [0.3.0] - 2026-10-21

### Added
- Upload several documents at once, with per-file results.
- "Screen documents on upload" setting (deferred screening still checks passages before generation).
- Explain decision panel showing each passage's score, page and reason.

## [0.2.0] - 2026-10-21

### Added
- First Windows installer: local chat and document questions with prompt and document screening, approved-only retrieval, encrypted records, source previews and saved conversations.

[1.0.0]: https://github.com/azibabdullah/secure-rag/releases/tag/v1.0.0
