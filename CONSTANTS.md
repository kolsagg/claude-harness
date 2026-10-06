# Constants
Never-changing values. Agent reads here instead of guessing.

| Name | Value | Note |
|------|-------|------|
| GitHub repo | `<owner>/claude-harness` | public (sahip kararı, 2026-10-06) |
| Hedef Claude dizini | `~/.claude` | Windows: `%USERPROFILE%\.claude` |
| Hedef Codex dizini | `~/.codex` | yalnız Codex = evet |
| Harici skill dizini | `~/.agents/skills` | `npx skills add -g` buraya kurar, `~/.claude/skills` altına link açar |
| Python | 3.10+ | install/export/doctor yalnız stdlib kullanır |
| Yer tutucu biçimi | `{{NAME}}` | koşullu blok: `<!-- if:vault -->` ... `<!-- endif:vault -->` |
