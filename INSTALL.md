# INSTALL (instructions for the agent)

You are a Claude Code agent. The user gave you this repository link and asked you to install or update their Claude Code harness. Follow the steps in order. Talk to the user in their language. Never print secrets. Never edit files under `~/.claude` by hand when `install.py` can do it.

Repo: `https://github.com/<owner>/claude-harness` (use the exact link the user gave you).

## 1. Check prerequisites

Run each command. If one fails, tell the user what is missing and offer the install command; do not continue until the required ones pass.

| Tool | Check | Required | Install hint |
|------|-------|----------|--------------|
| git | `git --version` | yes | Windows `winget install Git.Git`; macOS `xcode-select --install`; Linux `sudo apt install git` |
| Python 3.10+ | Windows `py -3 --version`; macOS/Linux `python3 --version` | yes | Windows `winget install Python.Python.3.12`; macOS `brew install python`; Linux `sudo apt install python3` |
| Node + npm | `node --version` and `npm --version` | yes (external skills, tools) | Windows `winget install OpenJS.NodeJS.LTS`; macOS `brew install node`; Linux use the distro package or nvm |
| Claude Code CLI | `claude --version` | yes (plugins) | `npm install -g @anthropic-ai/claude-code` or the official installer |
| GitHub CLI | `gh --version` | optional | Windows `winget install GitHub.cli`; macOS `brew install gh`; Linux `sudo apt install gh` |

In the commands below, `python` means `py -3` on Windows and `python3` elsewhere.

## 2. Get the repo

Use a stable location, `~/.claude-harness`.

```
git clone https://github.com/<owner>/claude-harness ~/.claude-harness
```

If `~/.claude-harness` already exists, update it instead:

```
git -C ~/.claude-harness pull --ff-only
```

## 3. Ask the user (one round)

Ask all questions in ONE round. If you have an AskUserQuestion-style tool, use it with all questions at once; otherwise ask them in a single message. Show each question to the user in both languages (Türkçe and English), exactly as below (the user may speak either).

1. `USER_NAME` — "Claude sana nasıl hitap etsin? (ad)" / "What should Claude call you? (first name)"
2. `LANGUAGE` — "Claude hangi dilde konuşsun ve belge yazsın? (İngilizce adıyla, ör. English, German)" / "Which language should Claude speak and write documents in? (English name, e.g. English, German)"
3. `GITHUB_OWNER` — "GitHub kullanıcı adın (yeni repolar bu hesaba açılır)" / "Your GitHub username (new repos are created under this account)"
4. `vault` — "Obsidian/beyin vault'u kurulu mu? Evetse yolu nedir?" / "Do you have an Obsidian/brain vault installed? If yes, what is its path?"
5. `orca` — "Orca kullanıyor musun?" / "Do you use Orca?"
6. `codex` — "Codex kullanıyor musun?" / "Do you use Codex?"
7. `permissions` — "Tehlikeli mod uyarısı atlansın ve izin modu 'auto' olsun mu? (varsayılan hayır)" / "Skip the dangerous-mode warning and set the permission mode to 'auto'? (default: no)"

The authoritative question texts live in `harness.json` under `questions`; if they differ from the above, prefer `harness.json` and still show both languages. Question 7 defaults to no: only enable it on an explicit yes.

## 4. Run the installer

Default way: write the answers to a JSON file with a quoted heredoc, then pass the file. A quoted heredoc (`<<'EOF'`) stops the shell from expanding `$`, backticks and quotes inside the user's text, so a name like `O'Brien` or a path with `$` cannot break the command or run anything.

macOS / Linux / Git Bash:

```
cat > /tmp/harness-answers.json <<'EOF'
{"USER_NAME": "Ada", "LANGUAGE": "English", "GITHUB_OWNER": "adaowner",
 "vault": "/path/to/your/vault", "orca": false, "codex": true, "permissions": false}
EOF
python3 ~/.claude-harness/install.py --answers /tmp/harness-answers.json --yes
```

Windows PowerShell (single-quoted here-string; the closing `'@` must start at column 0):

```
@'
{"USER_NAME": "Ada", "LANGUAGE": "English", "GITHUB_OWNER": "adaowner",
 "vault": "D:/notes/vault", "orca": false, "codex": true, "permissions": false}
'@ | Set-Content -Encoding utf8 $env:TEMP\harness-answers.json
py -3 $HOME\.claude-harness\install.py --answers $env:TEMP\harness-answers.json --yes
```

Answers file rules:

- `vault`: `false` (or a no-word) = no vault; a path string = vault at that path; `true` needs `VAULT_PATH` next to it. `VAULT_PATH` alone also works.
- `orca`, `codex`, `permissions`: JSON `true`/`false`, or the words yes/y/true/evet/e/1 and no/n/false/hayir/h/0. Any other value is an error (exit 2 with a message); nothing is installed.
- Required: `USER_NAME`, `LANGUAGE`, `GITHUB_OWNER`, `vault`, `orca`, `codex`. `permissions` is optional and defaults to false when missing in non-interactive mode (in a terminal the installer asks, default no).
- Never put API keys in the file.

Preview first with `--dry-run` if the user wants to see changes. Delete the answers file afterwards.

Secondary way, flags. Only use it when every value is plain and safe. WARNING: never put user-supplied text inside double quotes in a shell command (`"$name"`, `"$(...)"` and backticks are still evaluated); prefer the answers file above.

```
python ~/.claude-harness/install.py \
  --name Ada --language English --github-owner adaowner \
  --vault ~/notes/vault --no-orca --codex --no-permissions --yes
```

Flags: `--name --language --github-owner --vault PATH | --no-vault --orca/--no-orca --codex/--no-codex --permissions/--no-permissions --answers FILE --home DIR --skip-external --dry-run --yes`.

`--home DIR` pointing anywhere other than the real home directory turns the external steps off automatically (as if `--skip-external`) and prints a one-line notice, because `claude plugin`, `npm -g`, `pip --user` and `npx skills -g` always act on the real profile. Use it for sandbox runs only.

Exit codes: `0` ok; `2` answers are missing or invalid and there is no terminal to ask. On exit 2 the installer prints the missing questions as JSON on stdout (or an error line for an invalid value); ask the user those questions (step 3 wording), then re-run with the answers file. Any other non-zero code: show the user the last lines of output and stop.

What happens to existing files under `~/.claude`:

- Every file that changes is first backed up to `~/.claude/backups/claude-harness-<timestamp>/`.
- Content outside the managed block in `~/.claude/CLAUDE.md` is preserved.
- `settings.json`: the user's existing values are kept. The installer only writes a key that is absent, or one that still holds the value the harness wrote earlier (recorded in the state file); every kept key is listed in the report as "kept your value for <key>". `env`, `enabledPlugins`, `extraKnownMarketplaces`, `pluginConfigs` and `modelSettings` follow the same rule per sub-key (a plugin the user set to `false` stays `false`). Hooks are only added, never removed.
- A skill folder with the same name as one of the harness skills that the harness did not install is replaced (with a backup) and listed in the report as "replaced your skill <name>".
- `~/.codex/config.toml` is never overwritten, and it is not deleted if Codex is later switched off.
- Switching `permissions` from yes to no removes `skipDangerousModePermissionPrompt` and `permissions.defaultMode` only if they still hold the value the harness wrote; otherwise they are kept and reported.

Trust note for projects: the `proje-baslat` SessionStart hook only auto-runs dependency checks for projects the user listed as trusted (`python ~/.claude/skills/proje-baslat/doktor.py --trust <root>`). Never trust a repo cloned from someone else without the user's explicit yes.

## 5. Verify with doctor

```
python ~/.claude-harness/doctor.py
```

Exit `0` = healthy, `1` = something is red, `2` = not installed. Add `--json` for machine output and `--home DIR` for a non-default home. Lines are labelled TAMAM (green), HATA (red), UYARI (yellow), MANUEL (cannot verify automatically). Act on every red line: re-run `install.py` for missing files or plugins, fix the cause shown for failed steps (for example a missing network), then run doctor again. Report yellow and manual lines to the user; they are not failures. External steps that were skipped (`--skip-external`, or a non-default `--home`) show as yellow warnings, not red. A plugin the user disabled on purpose and the installer kept shows as yellow. A yellow "ccstatusline kurulu değil" line means: run `npm install -g ccstatusline`.

## 6. Steps you cannot do for the user

Tell the user, in their language:

- Log in: run `claude` once and complete the login.
- mem0 API key: run `/mem0 onboard` inside Claude Code. The shipped mem0 config uses a placeholder `user_id`; onboarding sets the user's own.
- Vault bridge (only if vault = yes): the brain bridge hooks come from the vault's own installer; run it from the vault root (see the vault's `AGENTS.md`). This repo does not install it. Doctor shows a yellow line until it is done.
- Orca (only if orca = yes): install the Orca desktop app; it installs its own hooks.
- Restart Claude Code so new settings, hooks and skills load.

## 7. Update flow

When the user asks to update the harness:

```
git -C ~/.claude-harness pull --ff-only
python ~/.claude-harness/install.py --yes
python ~/.claude-harness/doctor.py
```

`install.py` reads the answers of the last install back from the state file `~/.claude/.claude-harness.json` (`answers`), so a plain `python install.py --yes` is enough on an update. Flags and an answers file override the remembered values. Do not ask the user again unless something changed. Doctor prints a yellow "güncelleme var" line when the repo version is newer than the installed one. The installer is idempotent: values the user changed in `settings.json` are kept (see step 4), values the harness wrote and the user never touched are updated.

## 8. Cloud / remote environments (Claude Code on the web)

There is no terminal to answer questions, so use an answers file. In the environment setup script, clone and install non-interactively:

```
git clone https://github.com/<owner>/claude-harness ~/.claude-harness || git -C ~/.claude-harness pull --ff-only
cat > /tmp/harness-answers.json <<'EOF'
{"USER_NAME": "Ada", "LANGUAGE": "English", "GITHUB_OWNER": "adaowner",
 "vault": false, "orca": false, "codex": false, "permissions": false}
EOF
python3 ~/.claude-harness/install.py --answers /tmp/harness-answers.json --yes
python3 ~/.claude-harness/doctor.py
```

Cloud environments have no vault or Orca app, so keep `vault` and `orca` false. If the environment has no network access for npm, add `--skip-external` to `install.py`; external skills and npm tools are then skipped and doctor shows them as yellow warnings until installed. Keep secrets out of the setup script: never put API keys in the answers file.
