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
