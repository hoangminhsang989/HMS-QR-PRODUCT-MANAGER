# Open Design integration

R007B environment recovery: official `nexu-io/open-design` Windows x64 installer source was verified from the GitHub releases page, but the download was interrupted before completion (partial external file only; no install occurred). Therefore `OPEN_DESIGN_INSTALL_TYPE=NOT_INSTALLED`, `OPEN_DESIGN_PATH=NONE`, `OPEN_DESIGN_VERSION=UNKNOWN`, `CODEX_MCP_STATUS=BLOCKED_OPEN_DESIGN_NOT_INSTALLED`, and `OPEN_DESIGN_MCP_READ_TEST=NOT_RUN`. The Codex executable was discovered at `C:\Program Files\WindowsApps\OpenAI.Codex_26.803.10989.0_x64__2p2nqsd0c76g0\app\resources\codex.exe`, but direct PowerShell execution returned `Access is denied`; no reinstall or guessed configuration was attempted.

Pytest-qt recovery is complete: project configuration now routes `--basetemp`, `TEMP`, and `TMP` to the external TEST ROOT. Full suite result: `40 passed, 1 warning, 77.88s`; warning is unchanged external Starlette/httpx deprecation. Open Design remains optional and non-authoritative; synthetic data only, with no credentials or production/NAS paths.

## R007B1 official installer recovery

- `OPEN_DESIGN_RELEASE_TAG=open-design-v0.19.0` (official GitHub latest API; stable, non-draft, non-prerelease)
- `OPEN_DESIGN_ASSET_NAME=open-design-0.19.0-win-x64-setup.exe`
- `OPEN_DESIGN_ASSET_SIZE=330066405`
- `OPEN_DESIGN_ASSET_SHA256=D253518D29F44758FA200A2BF40589F3EE81A20ACC8ED5E3F2239FDAFA0BECF1`
- Asset source: official `nexu-io/open-design` GitHub release.
- Existing 133697360-byte interrupted file was classified `PARTIAL` with local SHA256 `C27ECAAFA0492B32903E3C80DD23C9A42A1BE95C1A27E7994F3DC765861562A8` and renamed individually outside the repository.
- Completed installer is outside production source under `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\tools\open-design`.
- Authenticode status is `NotSigned`, consistent with the upstream Windows-build warning; no security policy was disabled.

Installation/startup/MCP remain pending the required user confirmation immediately before running newly downloaded software.

## R007B1 installation and MCP result

- `OPEN_DESIGN_INSTALL_TYPE=STANDARD_PER_USER_WINDOWS_INSTALL`
- `OPEN_DESIGN_INSTALL_PATH=C:\Users\HMS-PCC\AppData\Local\Programs\Open Design`
- `OPEN_DESIGN_VERSION=0.19.0` from installed `Open Design.exe` file/product metadata and the running app release dialog.
- `OPEN_DESIGN_STARTUP_SMOKE=PASS`: window and workspace opened without an immediate crash.
- No `od` command is installed on PATH by the 0.19.0 Windows package.
- Official packaged equivalent used: `Open Design.exe --headless --mcp-install codex`.
- First invocation while Desktop was open exposed a packaged lifecycle conflict; Desktop was then closed normally and all owned processes were confirmed exited.
- Clean invocation reached the official Codex install endpoint but returned HTTP 500 `CODEX_INSTALL_FAILED` with exact message `spawn EPERM`.
- Codex config contains no Open Design MCP entry and Codex-side MCP resources/templates remain empty.

Therefore `CODEX_MCP_STATUS=BLOCKED_SPAWN_EPERM` and `OPEN_DESIGN_MCP_READ_TEST=NOT_RUN`. The WindowsApps ACL, packaged Codex executable, and Codex installation were not altered. Prototype and visual-evidence creation did not start because the authority gates them after real MCP PASS.

## R007B2 Codex Desktop recovery

Open Design Desktop Settings → Open Design MCP → Codex generated an exact client configuration. `OPEN_DESIGN_MCP_TRANSPORT=STDIO`. The generated command is the installed `Open Design.exe`; its arguments are the packaged `daemon-cli.mjs` plus `mcp`; generated environment values specify the release-stable data root, named-pipe daemon IPC path, headless bootstrap command/args, and `ELECTRON_RUN_AS_NODE=1`. Sanitized byte-for-byte evidence is stored outside the repository under `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\stage5\r007b2\open-design-mcp-generated-config.txt`.

The supported ChatGPT Desktop MCP Add Server form can represent this STDIO configuration, so direct `config.toml` fallback is not authorized. Saving/restarting ChatGPT Desktop is pending user action because the automation boundary prohibits controlling the ChatGPT/Codex app UI. `CODEX_MCP_RECOGNIZED`, initialization, and real MCP read remain pending; no PASS claim is made.
