# Penpot MCP integration — Stage 5 R007B4

Penpot is the intended canonical visual design authority for HMS QR. It must
remain development tooling only: production Desktop and Mobile runtime code
must not depend on Penpot, its MCP server, its plugin, or a Penpot account.

## Migration decision

- Open Design Cloud/AMR generation is retired from the Stage 5 hard gate after
  the zero-artifact insufficient-balance run. Open Design 0.19.0 remains
  optional historical tooling and is not retried or uninstalled.
- The zero-cost Penpot option is the official Penpot MCP server plus its
  connected Penpot plugin and a synthetic HMS QR design file.
- No Penpot account, MCP key, payment card, customer data, PO data, drawings,
  NAS files, or credentials were added during R007B4.

## Official source and expected topology

Source: `https://github.com/penpot/penpot`.

The current remote `develop`/HEAD observed during R007B4 is
`136052c15e12af700289df5f8abb3c95877abc24`. A bounded shallow checkout was
attempted under the external test-tools root, but did not complete; no Penpot
source is vendored in this repository.

The official documented local topology is:

```text
Codex MCP client → Penpot MCP server → Penpot MCP plugin → focused Penpot file
```

The documented local MCP endpoint is commonly `http://localhost:4401/mcp`,
but the live endpoint must be derived from the current server rather than
assumed. A server process alone is not a PASS.

## R007B4 live evidence

```text
PENPOT_MODE=NOT_CONNECTED
PENPOT_MCP_SOURCE_IDENTITY=official penpot/penpot (remote HEAD recorded)
PENPOT_MCP_SERVER=NOT_RUNNING
PENPOT_MCP_PLUGIN_CONNECTED=NOT_VERIFIED
PENPOT_MCP_RECOGNIZED=NOT_RUN
PENPOT_MCP_READ_TEST=NOT_RUN
PENPOT_MCP_WRITE_TEST=NOT_RUN
PENPOT_ZERO_COST_PATH=NOT_VERIFIED
```

R007B5 verified the official npm package metadata:

```text
PACKAGE=@penpot/mcp@2.15.4
SOURCE_REPOSITORY=https://github.com/penpot/penpot
BIN=penpot-mcp (bin/mcp-local.js)
```

Running `npx -y @penpot/mcp@stable` with portable Node `v22.23.2` did not
reach server startup. The package bootstrap invoked pnpm and stopped with
`ERR_PNPM_IGNORED_BUILDS` for `esbuild@0.25.12`, `esbuild@0.28.2`, and
`sharp@0.34.5`. This is the exact host package-policy blocker; ports 4400 and
4401 therefore remained unbound. The package tarball was inspected outside
production and confirmed to include the official server and plugin sources.

No build-script approval was granted automatically, no global policy was
changed, and no Penpot process or Codex MCP entry was started.

## R007B6 source-sparse release recovery

The official Penpot 2.17.0 `mcp` subtree was checked out sparsely under the
external tools root:

```text
commit=bdce5817ea86d028db29113d9ecdadcf07097b36
tree=936b5cfa08005172d7caff9ff754897afcf6dbf1
policy=allowBuilds esbuild=true sharp=false
packageManager=pnpm@11.9.0
```

Using portable Node 22.23.2 and the pinned package manager, dependency
installation and the official source build both passed. The live services
also passed transport checks:

```text
PENPOT_PLUGIN_SERVER=PASS
GET http://localhost:4400/manifest.json=200
PENPOT_MCP_PROCESS=PASS
PENPOT_MCP_ENDPOINT=http://localhost:4401/mcp
HEAD /mcp=405 (streamable POST endpoint; expected)
```

The remaining hard gate is the Penpot plugin attached to an active design file
and a standard free-account login. The browser reached
`https://design.penpot.app/#/auth/login`; no credentials were entered. Until
the user completes that normal login and opens a synthetic HMS QR file,
`PENPOT_PLUGIN_CONNECTED`, real read, real write, and readback remain
`NOT_RUN`.

Ports `localhost:4400` and `localhost:4401` were not listening during the
R007B4 preflight. No remote MCP URL or secret token was inserted into Codex
configuration. The next authorized recovery must start an official Penpot
environment, connect the plugin to a synthetic file, then configure Codex and
perform a read-only operation before any harmless write test.

## Design contract

Penpot artifacts must align with `DESIGN.md`, `apps/design_tokens.py`, Web CSS
variables, and the PySide6 theme. Penpot does not override business or QR
authorities. The QR payload remains exactly:

```text
product_name
customer_name
product_code
tracking_code
```

Visible label metadata is a separate presentation layer.

## R007B7C dual-identity verification

The user-level Codex configuration now carries two isolated remote identities:

```text
PENPOT_MODE=OFFICIAL_REMOTE_MCP
PENPOT_STAGE72_IDENTITY=penpot_stage72
PENPOT_HMS_QR_IDENTITY=penpot_hms_qr
PENPOT_STAGE72_URL=<REDACTED>
PENPOT_HMS_QR_URL=<REDACTED>
```

Both identities expose four live tools. Read-only binding proved the intended
parallel mapping without mutating the protected foreign project:

```text
penpot_stage72 -> HMS Stage72 Installer
penpot_hms_qr -> HMS QR PRODUCT MANAGER
PENPOT_TWO_PROJECT_PARALLEL_ISOLATION=PASS
FOREIGN_STAGE72_WRITE_COUNT=0
FOREIGN_STAGE72_DELETE_COUNT=0
FOREIGN_STAGE72_RENAME_COUNT=0
CROSS_PROJECT_ACCESS_VIOLATION_COUNT=0
```

The HMS QR target file was read, a disposable `R007B7_MCP_TEST` text object
was created and read back through `penpot_hms_qr`, then deleted. The stable
target identity observed during the run was file
`81f57451-85cc-819d-8008-7ad6c74d41f1`, page
`81f57451-85cc-819d-8008-7ad6c74d41f2`.

```text
PENPOT_HMS_QR_READ_TEST=PASS
PENPOT_HMS_QR_WRITE_TEST=PASS
PENPOT_HMS_QR_READBACK=PASS
PENPOT_DUAL_PROJECT_PARALLEL_GATE=PASS
```

The canonical file contains pages `00 DESIGN SYSTEM`, `01 DESKTOP`,
`02 MOBILE`, `03 HISTORY`, and `04 QR LABELS`, with artifacts A–G. These
artifacts are synthetic design authority only; production runtime remains
independent of Penpot. UICanvas remains optional non-product tooling.

## R007B7D light-theme override

The current canonical/default visual direction is light industrial. Any prior
dark Penpot export is historical and must not be used as Stage 5 acceptance
evidence. The refreshed file must use the same light semantic values as
`apps/design_tokens.py`: soft warm-neutral background, white panels, light-gray
raised surfaces, dark charcoal text, neutral borders, blue accent, and semantic
success/warning/danger/info colors. The QR label remains white/light with dark
text and a printer-safe black QR mark.

```text
CANONICAL_THEME=LIGHT
DESKTOP_LIGHT_THEME_REVIEW=PASS
MOBILE_LIGHT_THEME_REVIEW=PASS
PENPOT_LIGHT_ARTIFACT_REFRESH=PASS
```
