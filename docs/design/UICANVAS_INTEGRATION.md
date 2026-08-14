# UICanvas Local MCP integration — Stage 5 R007B4

UICanvas is the rapid local prototype and screenshot canvas. It is not the
canonical design store and is not a production runtime dependency.

## Source and environment

```text
UICANVAS_SOURCE=https://github.com/markvely/uicanvas
UICANVAS_COMMIT=ec17dd0bb889dc9868a83aa04218a66575aade64
UICANVAS_PACKAGE_VERSION=1.3.1
UICANVAS_LICENSE=MIT
UICANVAS_NODE=v24.18.0
UICANVAS_NPM=12.0.1
UICANVAS_INSTALL_ROOT=F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\tools\uicanvas
```

The checkout and `node_modules` are outside the HMS QR production repository.
No UICanvas source, cache, screenshot, or runtime data may be committed here.

## Intended local workflow

The upstream workflow is:

```text
node server.js              # browser canvas at localhost:3200
node server.js --stdio      # MCP stdio server for the connected canvas
```

The Codex MCP entry must use the exact local Node executable, the absolute
`server.js` path, and `--stdio`; it must be added only after a live local smoke
test and with the existing user configuration backed up. UICanvas MCP tools
must be used directly (`init_project`, `create_artboard`, `write_html`,
`get_basic_info`, `get_screenshot`, or the exact names exposed by the checked
out server). Homemade WebSocket bridges and direct canvas socket calls are
not allowed.

## R007B4 live evidence

```text
UICANVAS_LOCAL_INSTALL=PASS
UICANVAS_DEPENDENCIES=PASS
UICANVAS_LOCAL_SERVER=BLOCKED_UPSTREAM_WINDOWS_RUNTIME
UICANVAS_BROWSER_CANVAS=NOT_RUN
UICANVAS_MCP_RECOGNIZED=NOT_RUN
UICANVAS_MCP_REAL_TOOL_TEST=NOT_RUN
UICANVAS_ARTIFACT_A_TO_G=NOT_RUN
```

The checked-out server's live registration contains these tool names:

```text
open_canvas
init_project
finalize_design_spec
get_basic_info
create_artboard
write_html
get_children
get_styles
get_tree
get_node_info
delete_nodes
update_styles
set_text
get_screenshot
duplicate_nodes
insert_image
```

`open_canvas` is an explicit prerequisite before `init_project`,
`create_artboard`, or `write_html`; therefore a real MCP tool test cannot be
truthfully performed without a connected browser canvas.

On this Windows host, the official `node server.js --port 3200` process exits
cleanly after printing its informational stdio hint and does not bind port
3200. Foreground evidence was captured under the R007B5 test root. The same
unmodified checkout was then run with official portable Node `v22.23.2` and
produced the identical exit-without-listen result. This rejects a Node24-only
hypothesis. No application exception or listening process was observed. The
third-party checkout was not patched and no custom bridge was created.

Recovery requires an upstream-compatible UICanvas Windows startup path or a
fresh bounded authority to investigate the upstream behavior. Until then,
UICanvas and Penpot prototype gates remain truthful `NOT_RUN`/`BLOCKED` states.

## R007B6 extension-host topology

An existing VS Code installation was found and launched against the synthetic
workspace `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\stage5\r007b6\uicanvas-host-workspace`.
The UICanvas activity-bar view appeared, and the extension wrote a dynamic
port-file value (`10962`). A Windows Defender Firewall prompt then appeared
while the extension attempted to open its HTTP listener. The security prompt
was not automated or changed, so the listener and Webview connection were not
claimed as PASS.

```text
UICANVAS_EXTENSION_HOST=VS_CODE
UICANVAS_EXTENSION_ACTIVATION=PARTIAL_FIREWALL_PROMPT
UICANVAS_HTTP_PORT=10962 (port-file observation only)
UICANVAS_LOCAL_SERVER=NOT_VERIFIED
UICANVAS_HEALTH=NOT_RUN
UICANVAS_WEBVIEW_CONNECTED=NOT_RUN
UICANVAS_MCP_REAL_TOOL_TEST=NOT_RUN
UICANVAS_STATUS=OPTIONAL_TOOLING_BLOCKER_NON_PRODUCT
```

R007B6 permits Penpot to remain the hard gate if UICanvas cannot be completed
without changing Windows security settings or patching the upstream checkout.
