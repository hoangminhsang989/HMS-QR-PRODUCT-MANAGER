"""Next-Gen Industrial Control Portal for HMS QR Product Manager."""

from __future__ import annotations
from base64 import b64encode
from io import BytesIO
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import urllib.parse
from fastapi.responses import HTMLResponse
import qrcode

from apps.server.tls import lan_url_scheme

from apps.design_tokens import WEB_CSS_VARS
from config.paths import PathConfigurationError, require_test_root
from packages.qr.payload import QrPayload
from packages.qr.service import QRService


def _resolve_db_path() -> Path:
    """Resolve SQLite database path from env/config, falling back to known dev path."""
    # Prefer explicit database URL env var
    db_url = os.environ.get("HMS_QR_DATABASE_URL", "")
    if db_url.startswith("sqlite:///"):
        p = Path(db_url[len("sqlite:///"):])
        if p.is_file():
            return p
    # Derive from HMS_QR_TEST_ROOT
    test_root = os.environ.get("HMS_QR_TEST_ROOT", "")
    if test_root:
        p = Path(test_root) / "db" / "stage1_r002_dev.sqlite"
        if p.is_file():
            return p
    # Structural fallback through the shared path configuration (no host literals)
    try:
        return require_test_root() / "db" / "stage1_r002_dev.sqlite"
    except PathConfigurationError:
        return Path("stage1_r002_dev.sqlite")


def get_public_tunnel_url() -> str | None:
    log_path = Path(tempfile.gettempdir()) / "cloudflared.log"
    if log_path.is_file():
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
            if match:
                return match.group(0)
        except Exception:
            pass
    return None


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def make_qr_data_uri(text: str) -> str:
    buf = BytesIO()
    qrcode.make(text).save(buf, format="PNG")
    return f"data:image/png;base64,{b64encode(buf.getvalue()).decode('ascii')}"


def format_qty(val) -> str:
    if val is None or val == "":
        return ""
    try:
        f = float(val)
        return str(int(f)) if f.is_integer() else f"{f:g}"
    except Exception:
        return str(val)


def get_live_events() -> list[dict]:
    db_path = _resolve_db_path()
    if not db_path.is_file():
        return []
    try:
        import sqlite3
        conn = sqlite3.connect(db_path.as_posix())
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        reports = cur.execute("""
            SELECT r.server_timestamp, r.actor_display_name_snapshot as actor,
                   coalesce(m.display_name, 'Gia công') as action,
                   case when r.attempt_number is not null then 'Lần ' || r.attempt_number else 'Đã xong' end as detail,
                   r.quantity, r.notes, p.part_name, t.tracking_code, 'PROCESS' as category
            FROM process_report_events r
            LEFT JOIN machining_types m ON r.machining_type_id = m.internal_id
            LEFT JOIN order_tracking_items t ON r.tracking_item_id = t.internal_id
            LEFT JOIN products p ON t.product_id = p.internal_id
            ORDER BY r.server_timestamp DESC
            LIMIT 25
        """).fetchall()
        workflows = cur.execute("""
            SELECT w.server_timestamp, w.actor_display_name_snapshot as actor,
                   w.event_type as action, 'Quy trình QC/Giao' as detail,
                   w.quantity, w.notes, p.part_name, t.tracking_code, 'WORKFLOW' as category
            FROM tracking_workflow_events w
            LEFT JOIN order_tracking_items t ON w.tracking_item_id = t.internal_id
            LEFT JOIN products p ON t.product_id = p.internal_id
            ORDER BY w.server_timestamp DESC
            LIMIT 25
        """).fetchall()
        combined = []
        for item in sorted([dict(r) for r in reports] + [dict(w) for w in workflows], key=lambda x: str(x["server_timestamp"]), reverse=True)[:20]:
            item["quantity"] = format_qty(item.get("quantity"))
            combined.append(item)
        conn.close()
        return combined
    except Exception:
        return []


def get_stats() -> dict[str, int]:
    db_path = _resolve_db_path()
    if not db_path.is_file():
        return {"products": 0, "pos": 0, "tracking": 0, "operators": 0, "machining": 7, "in_prod": 0, "qc": 0, "packed": 0, "deliv": 0}
    try:
        import sqlite3
        conn = sqlite3.connect(db_path.as_posix())
        cur = conn.cursor()
        prods = cur.execute("SELECT count(*) FROM products").fetchone()[0]
        pos = cur.execute("SELECT count(*) FROM purchase_orders").fetchone()[0]
        tracking = cur.execute("SELECT count(*) FROM order_tracking_items").fetchone()[0]
        ops = cur.execute("SELECT count(*) FROM operators").fetchone()[0]
        sc = dict(cur.execute("SELECT status, count(*) FROM order_tracking_items GROUP BY status").fetchall())
        conn.close()
        return {
            "products": prods, "pos": pos, "tracking": tracking, "operators": ops, "machining": 7,
            "in_prod": sc.get("IN_PRODUCTION", 0),
            "qc": sc.get("QC_CHECKED", 0),
            "packed": sc.get("PACKED", 0),
            "deliv": sc.get("DELIVERED", 0),
        }
    except Exception:
        return {"products": 76, "pos": 75, "tracking": 76, "operators": 3, "machining": 7, "in_prod": 75, "qc": 1, "packed": 0, "deliv": 0}


_SS_JS = r"""

    // ══════════════════════════════════════════════════════════════════════════
    // HMS QR — EXCEL-GRADE SPREADSHEET ENGINE v2.0
    // Features: multi-select, resize col, freeze header, fill-down/right,
    //   autofill drag, format (number/currency/date/%), bold/italic/color,
    //   insert/delete row+col with formula update, context menu, undo/redo,
    //   full Excel-compatible copy/paste (Clipboard API + TSV), 80+ formulas
    // ══════════════════════════════════════════════════════════════════════════

    // ─── CONSTANTS ────────────────────────────────────────────────────────────
    const SS_COLS = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T'];
    const SS_DEFAULT_ROWS = 30;
    const SS_DEFAULT_COLS = 10;
    const SS_COL_HEADERS  = ['Khách hàng','Tên chi tiết','Số lượng','ĐVT','Vật liệu','Xử lý bề mặt','Kích thước','Đơn giá','Ghi chú','Dự phòng'];
    const SS_COL_WIDTHS_DEFAULT = [120,200,80,60,110,120,110,90,130,90];

    // ─── STATE ────────────────────────────────────────────────────────────────
    let ssRows = SS_DEFAULT_ROWS;
    let ssCols = SS_DEFAULT_COLS;

    // ssData[r][c] = { raw:'', value:'', fmt:'', bold:false, italic:false, color:'', bg:'' }
    let ssData = [];
    let ssColWidths = [...SS_COL_WIDTHS_DEFAULT];

    // Selection
    let ssSelR1=0, ssSelC1=0, ssSelR2=0, ssSelC2=0;   // anchor..active
    let ssEditMode = false;
    let ssMouseDown = false;

    // Undo/Redo
    let ssUndoStack = [], ssRedoStack = [];
    const SS_UNDO_MAX = 50;

    // AutoFill drag
    let ssFillDragging = false, ssFillStartR=0, ssFillStartC=0;

    // Column resize drag
    let ssResizingCol = -1, ssResizeStartX = 0, ssResizeStartW = 0;

    // Preview items (for import)
    let ssLastPreviewItems = [];

    // ─── INIT ─────────────────────────────────────────────────────────────────
    function ssInit() {
      ssData = Array.from({length: ssRows}, () =>
        Array.from({length: ssCols}, () => ({raw:'', value:'', fmt:'general', bold:false, italic:false, color:'', bg:''}))
      );
      ssColWidths = ssCols <= SS_COL_WIDTHS_DEFAULT.length
        ? SS_COL_WIDTHS_DEFAULT.slice(0, ssCols)
        : [...SS_COL_WIDTHS_DEFAULT, ...Array(ssCols - SS_COL_WIDTHS_DEFAULT.length).fill(90)];
      ssUndoStack = []; ssRedoStack = [];
      ssSelR1=ssSelR2=0; ssSelC1=ssSelC2=0;
      ssRender();
      ssFocusCell(0,0);
    }

    // ─── RENDER ───────────────────────────────────────────────────────────────
    function ssRender() {
      ssRenderHeader();
      ssRenderBody();
      ssCellRefUpdate();
    }

    function ssRenderHeader() {
      const thead = document.getElementById('ss-thead');
      if (!thead) return;
      let h = '<tr><th class="ss-corner"></th>';
      for (let c=0; c<ssCols; c++) {
        h += `<th class="ss-col-header" data-col="${c}" style="width:${ssColWidths[c]}px;min-width:${ssColWidths[c]}px;">
          <div class="ss-col-header-inner">
            <span>${SS_COLS[c]}</span>
            <div class="ss-col-sub">${SS_COL_HEADERS[c]||''}</div>
          </div>
          <div class="ss-col-resize" data-col="${c}" onmousedown="ssResizeStart(event,${c})"></div>
        </th>`;
      }
      h += '</tr>';
      thead.innerHTML = h;
    }

    function ssRenderBody() {
      const tbody = document.getElementById('ss-tbody');
      if (!tbody) return;
      let h = '';
      for (let r=0; r<ssRows; r++) {
        h += `<tr data-row="${r}"><td class="ss-row-header">${r+1}</td>`;
        for (let c=0; c<ssCols; c++) {
          h += ssCellHtml(r, c);
        }
        h += '</tr>';
      }
      tbody.innerHTML = h;
      // Attach events after render
      tbody.querySelectorAll('td.ss-cell').forEach(td => {
        td.addEventListener('mousedown',  ssOnCellMouseDown);
        td.addEventListener('mousemove',  ssOnCellMouseMove);
        td.addEventListener('mouseup',    ssOnCellMouseUp);
        td.addEventListener('dblclick',   ssOnCellDblClick);
        td.addEventListener('contextmenu',ssShowContextMenu);
      });
      tbody.querySelectorAll('.ss-fill-handle').forEach(el => {
        el.addEventListener('mousedown', ssFillHandleDown);
      });
      ssHighlightSelection();
    }

    function ssCellHtml(r, c) {
      const cell = ssData[r]?.[c] || {};
      const disp = ssFormatDisplay(cell.value !== '' ? cell.value : cell.raw, cell.fmt || 'general');
      const isNum = !isNaN(parseFloat(cell.value)) && cell.value !== '';
      const align = cell.align || (isNum ? 'right' : 'left');
      const style = [
        `width:${ssColWidths[c]}px;max-width:${ssColWidths[c]}px;`,
        cell.bold      ? 'font-weight:700;' : '',
        cell.italic    ? 'font-style:italic;' : '',
        cell.underline ? 'text-decoration:underline;' : '',
        cell.color     ? `color:${cell.color};` : '',
        cell.bg        ? `background:${cell.bg};` : '',
        cell.wrap      ? 'white-space:normal;overflow:visible;height:auto;' : '',
        `text-align:${align};`,
      ].join('');
      const isFillHandle = (r === ssSelR2 && c === ssSelC2);
      return `<td class="ss-cell" data-r="${r}" data-c="${c}" style="${style}">
        <span class="ss-cell-text"${cell.wrap ? ' style="white-space:normal;overflow:visible;text-overflow:clip;"' : ''}>${escHtml(String(disp))}</span>${isFillHandle?'<div class="ss-fill-handle"></div>':''}
      </td>`;
    }

    function escHtml(s) {
      return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    // ─── SELECTION ────────────────────────────────────────────────────────────
    function ssHighlightSelection() {
      document.querySelectorAll('.ss-cell').forEach(td => {
        td.classList.remove('ss-selected','ss-active','ss-sel-top','ss-sel-bottom','ss-sel-left','ss-sel-right');
        const r=+td.dataset.r, c=+td.dataset.c;
        const inSel = r>=Math.min(ssSelR1,ssSelR2) && r<=Math.max(ssSelR1,ssSelR2)
                   && c>=Math.min(ssSelC1,ssSelC2) && c<=Math.max(ssSelC1,ssSelC2);
        if (inSel) {
          td.classList.add('ss-selected');
          const rMin=Math.min(ssSelR1,ssSelR2), rMax=Math.max(ssSelR1,ssSelR2);
          const cMin=Math.min(ssSelC1,ssSelC2), cMax=Math.max(ssSelC1,ssSelC2);
          if (r===rMin) td.classList.add('ss-sel-top');
          if (r===rMax) td.classList.add('ss-sel-bottom');
          if (c===cMin) td.classList.add('ss-sel-left');
          if (c===cMax) td.classList.add('ss-sel-right');
        }
        if (r===ssSelR2 && c===ssSelC2) td.classList.add('ss-active');
      });
      // fill handle: only on active cell
      document.querySelectorAll('.ss-fill-handle').forEach(el => el.remove());
      const activeCell = document.querySelector(`.ss-cell[data-r="${ssSelR2}"][data-c="${ssSelC2}"]`);
      if (activeCell && !ssEditMode) {
        const fh = document.createElement('div');
        fh.className = 'ss-fill-handle';
        fh.addEventListener('mousedown', ssFillHandleDown);
        activeCell.appendChild(fh);
      }
      ssUpdateAggregate();
      ssCellRefUpdate();
    }

    function ssFocusCell(r, c, extend=false) {
      if (ssEditMode) ssCommitEdit();
      if (r<0) r=0; if (r>=ssRows) r=ssRows-1;
      if (c<0) c=0; if (c>=ssCols) c=ssCols-1;
      if (extend) { ssSelR2=r; ssSelC2=c; }
      else { ssSelR1=r; ssSelC1=c; ssSelR2=r; ssSelC2=c; }
      ssHighlightSelection();
      ssScrollIntoView(r, c);
      const formulaBar = document.getElementById('ss-formula-bar');
      if (formulaBar) formulaBar.value = ssData[r]?.[c]?.raw || '';
      ssUpdateRibbonState();
    }

    function ssScrollIntoView(r, c) {
      const cell = document.querySelector(`.ss-cell[data-r="${r}"][data-c="${c}"]`);
      if (cell) cell.scrollIntoView({block:'nearest',inline:'nearest'});
    }

    function ssCellRefUpdate() {
      const el = document.getElementById('ss-cell-addr');
      if (!el) return;
      const rMin=Math.min(ssSelR1,ssSelR2), rMax=Math.max(ssSelR1,ssSelR2);
      const cMin=Math.min(ssSelC1,ssSelC2), cMax=Math.max(ssSelC1,ssSelC2);
      if (rMin===rMax && cMin===cMax) {
        el.textContent = SS_COLS[ssSelC2]+(ssSelR2+1);
      } else {
        el.textContent = `${SS_COLS[cMin]}${rMin+1}:${SS_COLS[cMax]}${rMax+1}`;
      }
      const bar = document.getElementById('ss-formula-bar');
      if (bar && !ssEditMode) bar.value = ssData[ssSelR2]?.[ssSelC2]?.raw || '';
    }

    // ─── MOUSE EVENTS ─────────────────────────────────────────────────────────
    function ssOnCellMouseDown(e) {
      if (e.button !== 0) return;
      const r=+this.dataset.r, c=+this.dataset.c;
      if (ssEditMode) ssCommitEdit();
      ssMouseDown = true;
      if (e.shiftKey) { ssSelR2=r; ssSelC2=c; }
      else            { ssSelR1=r; ssSelC1=c; ssSelR2=r; ssSelC2=c; }
      ssHighlightSelection();
      e.preventDefault();
    }
    function ssOnCellMouseMove(e) {
      if (!ssMouseDown) return;
      const r=+this.dataset.r, c=+this.dataset.c;
      ssSelR2=r; ssSelC2=c;
      ssHighlightSelection();
    }
    function ssOnCellMouseUp(e) { ssMouseDown=false; }
    document.addEventListener('mouseup', ()=>{ ssMouseDown=false; ssFillDragging=false; ssResizingCol=-1; });

    function ssOnCellDblClick(e) {
      const r=+this.dataset.r, c=+this.dataset.c;
      ssSelR1=ssSelR2=r; ssSelC1=ssSelC2=c;
      ssStartEdit(r, c);
    }

    // ─── EDIT ─────────────────────────────────────────────────────────────────
    function ssStartEdit(r, c, initChar='') {
      if (ssEditMode) ssCommitEdit();
      ssEditMode = true;
      const cell = ssData[r]?.[c];
      const td = document.querySelector(`.ss-cell[data-r="${r}"][data-c="${c}"]`);
      if (!td) return;
      td.innerHTML = `<input id="ss-cell-input" type="text" autocomplete="off"
        style="width:100%;height:100%;background:var(--card);color:var(--text);border:none;outline:none;padding:2px 4px;font-size:13px;font-family:inherit;">`;
      const inp = td.querySelector('#ss-cell-input');
      inp.value = initChar || (cell?.raw || '');
      inp.focus();
      if (!initChar) inp.select(); else { inp.setSelectionRange(inp.value.length, inp.value.length); }
      inp.oninput = () => {
        const bar = document.getElementById('ss-formula-bar');
        if (bar) bar.value = inp.value;
      };
      inp.onkeydown = ssInputKeyDown;
      inp.onblur = () => { if (ssEditMode) ssCommitEdit(); };
      const bar = document.getElementById('ss-formula-bar');
      if (bar) { bar.value = inp.value; }
    }

    function ssCommitEdit() {
      if (!ssEditMode) return;
      const inp = document.getElementById('ss-cell-input');
      if (inp) {
        const r=ssSelR2, c=ssSelC2;
        const raw = inp.value;
        ssSaveUndo();
        ssSetRaw(r, c, raw);
      }
      ssEditMode = false;
      ssRecomputeAll();
      ssRenderBody();
      ssHighlightSelection();
    }

    function ssSetRaw(r, c, raw) {
      if (!ssData[r]?.[c]) return;
      ssData[r][c].raw = raw;
      ssData[r][c].value = raw.startsWith('=') ? ssEvalFormula(raw.slice(1), r, c) : raw;
    }

    function ssRecomputeAll() {
      for (let r=0; r<ssRows; r++)
        for (let c=0; c<ssCols; c++) {
          const raw = ssData[r]?.[c]?.raw || '';
          if (raw.startsWith('=')) ssData[r][c].value = ssEvalFormula(raw.slice(1), r, c);
        }
    }

    // ─── KEYBOARD ─────────────────────────────────────────────────────────────
    function ssInputKeyDown(e) {
      if (e.key==='Enter')  { e.preventDefault(); ssCommitEdit(); ssFocusCell(ssSelR2+1, ssSelC2); }
      else if (e.key==='Tab')    { e.preventDefault(); ssCommitEdit(); ssFocusCell(ssSelR2, ssSelC2+(e.shiftKey?-1:1)); }
      else if (e.key==='Escape') { ssEditMode=false; ssRecomputeAll(); ssRenderBody(); ssHighlightSelection(); }
      else if (e.key==='F2')     { /* stay in edit */ }
    }

    document.addEventListener('keydown', ssGridKeyDown);
    function ssGridKeyDown(e) {
      // Ignore if typing in formula bar or other inputs
      if (e.target.id==='ss-formula-bar' || e.target.id==='ss-cell-input') return;
      if (e.target.tagName==='INPUT' || e.target.tagName==='TEXTAREA' || e.target.tagName==='SELECT') return;
      // Only act if spreadsheet is visible
      const container = document.getElementById('ss-container');
      if (!container || container.offsetParent===null) return;

      const r=ssSelR2, c=ssSelC2;
      const ctrl = e.ctrlKey || e.metaKey;

      if (ctrl && e.key==='z') { e.preventDefault(); ssUndo(); return; }
      if (ctrl && e.key==='y') { e.preventDefault(); ssRedo(); return; }
      if (ctrl && e.key==='c') { e.preventDefault(); ssCopyToClipboard(); return; }
      if (ctrl && e.key==='x') { e.preventDefault(); ssCutToClipboard(); return; }
      if (ctrl && e.key==='v') { e.preventDefault(); ssPasteFromClipboard(); return; }
      if (ctrl && e.key==='d') { e.preventDefault(); ssFillDown(); return; }
      if (ctrl && e.key==='r') { e.preventDefault(); ssFillRight(); return; }
      if (ctrl && e.key==='b') { e.preventDefault(); ssToggleBold(); return; }
       if (ctrl && e.key==='i') { e.preventDefault(); ssToggleItalic(); return; }
       if (ctrl && e.key==='u') { e.preventDefault(); ssToggleUnderline(); return; }
      if (ctrl && e.key==='Home') { e.preventDefault(); ssFocusCell(0,0); return; }
      if (ctrl && e.key==='End') { e.preventDefault(); ssFocusCell(ssRows-1, ssCols-1); return; }
      if (ctrl && e.key==='ArrowDown') { e.preventDefault(); ssFocusCell(ssRows-1, c, e.shiftKey); return; }
      if (ctrl && e.key==='ArrowUp') { e.preventDefault(); ssFocusCell(0, c, e.shiftKey); return; }
      if (ctrl && e.key==='ArrowRight') { e.preventDefault(); ssFocusCell(r, ssCols-1, e.shiftKey); return; }
      if (ctrl && e.key==='ArrowLeft') { e.preventDefault(); ssFocusCell(r, 0, e.shiftKey); return; }

      if (e.key==='ArrowUp')    { e.preventDefault(); ssFocusCell(r-1, c, e.shiftKey); return; }
      if (e.key==='ArrowDown')  { e.preventDefault(); ssFocusCell(r+1, c, e.shiftKey); return; }
      if (e.key==='ArrowLeft')  { e.preventDefault(); ssFocusCell(r, c-1, e.shiftKey); return; }
      if (e.key==='ArrowRight') { e.preventDefault(); ssFocusCell(r, c+1, e.shiftKey); return; }
      if (e.key==='Tab')   { e.preventDefault(); ssFocusCell(r, c+(e.shiftKey?-1:1)); return; }
      if (e.key==='Enter') { e.preventDefault(); ssFocusCell(r+1, c); return; }
      if (e.key==='Delete'||e.key==='Backspace') {
        e.preventDefault();
        ssSaveUndo();
        ssDeleteSelection();
        return;
      }
      if (e.key==='F2') { e.preventDefault(); ssStartEdit(r,c); return; }

      // Any printable char starts edit
      if (e.key.length===1 && !ctrl) {
        e.preventDefault();
        ssStartEdit(r, c, e.key);
      }
    }

    // ─── FORMULA BAR ──────────────────────────────────────────────────────────
    function ssFormulaBarInput() {
      const bar = document.getElementById('ss-formula-bar');
      if (!bar) return;
      if (!ssEditMode) {
        ssEditMode = true;
        // Reflect into cell input if exists
      }
      const inp = document.getElementById('ss-cell-input');
      if (inp) inp.value = bar.value;
    }

    function ssFormulaBarKeyDown(e) {
      if (e.key==='Enter') {
        e.preventDefault();
        const bar = document.getElementById('ss-formula-bar');
        if (bar) {
          ssSaveUndo();
          ssSetRaw(ssSelR2, ssSelC2, bar.value);
          ssEditMode = false;
          ssRecomputeAll();
          ssRenderBody();
          ssHighlightSelection();
          ssFocusCell(ssSelR2+1, ssSelC2);
        }
      } else if (e.key==='Escape') {
        ssEditMode = false;
        const bar = document.getElementById('ss-formula-bar');
        if (bar) bar.value = ssData[ssSelR2]?.[ssSelC2]?.raw || '';
      }
    }

    // ─── DELETE SELECTION ─────────────────────────────────────────────────────
    function ssDeleteSelection() {
      const rMin=Math.min(ssSelR1,ssSelR2), rMax=Math.max(ssSelR1,ssSelR2);
      const cMin=Math.min(ssSelC1,ssSelC2), cMax=Math.max(ssSelC1,ssSelC2);
      for (let r=rMin; r<=rMax; r++)
        for (let c=cMin; c<=cMax; c++)
          if (ssData[r]?.[c]) { ssData[r][c].raw=''; ssData[r][c].value=''; }
      ssRecomputeAll();
      ssRenderBody();
      ssHighlightSelection();
    }

    // ─── UNDO/REDO ────────────────────────────────────────────────────────────
    function ssSaveUndo() {
      ssUndoStack.push(JSON.stringify(ssData));
      if (ssUndoStack.length > SS_UNDO_MAX) ssUndoStack.shift();
      ssRedoStack = [];
    }
    function ssUndo() {
      if (!ssUndoStack.length) return;
      ssRedoStack.push(JSON.stringify(ssData));
      ssData = JSON.parse(ssUndoStack.pop());
      ssRows = ssData.length; ssCols = ssData[0]?.length || ssCols;
      ssRecomputeAll(); ssRenderBody(); ssHighlightSelection();
      document.getElementById('ss-status').textContent='↩ Đã hoàn tác';
    }
    function ssRedo() {
      if (!ssRedoStack.length) return;
      ssUndoStack.push(JSON.stringify(ssData));
      ssData = JSON.parse(ssRedoStack.pop());
      ssRows = ssData.length; ssCols = ssData[0]?.length || ssCols;
      ssRecomputeAll(); ssRenderBody(); ssHighlightSelection();
      document.getElementById('ss-status').textContent='↪ Đã làm lại';
    }

    // ─── COPY / PASTE / CUT ───────────────────────────────────────────────────
    function ssGetSelectionTSV(useRaw=false) {
      const rMin=Math.min(ssSelR1,ssSelR2), rMax=Math.max(ssSelR1,ssSelR2);
      const cMin=Math.min(ssSelC1,ssSelC2), cMax=Math.max(ssSelC1,ssSelC2);
      const lines = [];
      for (let r=rMin; r<=rMax; r++) {
        const cells = [];
        for (let c=cMin; c<=cMax; c++) {
          const cell = ssData[r]?.[c];
          cells.push(useRaw ? (cell?.raw||'') : ssFormatDisplay(cell?.value!==''?cell?.value:cell?.raw, cell?.fmt||'general'));
        }
        lines.push(cells.join('\t'));
      }
      return lines.join('\r\n');
    }

    function ssCopyToClipboard() {
      const tsv = ssGetSelectionTSV(false);
      navigator.clipboard.writeText(tsv).then(() => {
        ssSetStatus('📋 Đã copy — có thể dán vào Excel');
      }).catch(() => {
        ssSetStatus('❌ Không có quyền clipboard');
      });
    }

    function ssCutToClipboard() {
      ssCopyToClipboard();
      ssSaveUndo();
      ssDeleteSelection();
    }

    function ssPasteFromClipboard() {
      navigator.clipboard.readText().then(text => {
        if (!text) return;
        ssPasteTSV(text);
      }).catch(() => {
        ssSetStatus('❌ Không thể đọc clipboard — thử Ctrl+Shift+V');
      });
    }

    function ssPasteTSV(text) {
      ssSaveUndo();
      const lines = text.replace(/\r\n/g,'\n').replace(/\r/g,'\n').split('\n');
      if (lines[lines.length-1]==='') lines.pop();
      const r0=ssSelR2, c0=ssSelC2;
      // Expand grid if needed
      const needR = r0 + lines.length;
      const needC = c0 + (lines[0]?.split('\t').length||0);
      if (needR > ssRows) { while(ssData.length<needR) ssData.push(Array.from({length:ssCols},()=>({raw:'',value:'',fmt:'general',bold:false,italic:false,color:'',bg:''}))); ssRows=ssData.length; }
      if (needC > ssCols) { ssData.forEach(row=>{while(row.length<needC)row.push({raw:'',value:'',fmt:'general',bold:false,italic:false,color:'',bg:''});}); ssCols=needC; ssColWidths=[...ssColWidths,...Array(needC-ssColWidths.length).fill(90)]; }
      lines.forEach((line, ri) => {
        const cells = line.split('\t');
        cells.forEach((val, ci) => {
          const r=r0+ri, c=c0+ci;
          ssSetRaw(r, c, val);
        });
      });
      ssSelR1=r0; ssSelC1=c0; ssSelR2=r0+lines.length-1; ssSelC2=c0+(lines[0].split('\t').length)-1;
      ssRecomputeAll();
      ssRenderBody();
      ssHighlightSelection();
      ssSetStatus(`✅ Đã dán ${lines.length} hàng`);
    }

    // ─── FILL DOWN / RIGHT ────────────────────────────────────────────────────
    function ssFillDown() {
      ssSaveUndo();
      const rMin=Math.min(ssSelR1,ssSelR2), rMax=Math.max(ssSelR1,ssSelR2);
      const cMin=Math.min(ssSelC1,ssSelC2), cMax=Math.max(ssSelC1,ssSelC2);
      for (let c=cMin; c<=cMax; c++) {
        const srcRaw = ssData[rMin]?.[c]?.raw||'';
        for (let r=rMin+1; r<=rMax; r++) ssSetRaw(r, c, ssShiftFormula(srcRaw, r-rMin, 0));
      }
      ssRecomputeAll(); ssRenderBody(); ssHighlightSelection();
      ssSetStatus('↓ Fill Down');
    }

    function ssFillRight() {
      ssSaveUndo();
      const rMin=Math.min(ssSelR1,ssSelR2), rMax=Math.max(ssSelR1,ssSelR2);
      const cMin=Math.min(ssSelC1,ssSelC2), cMax=Math.max(ssSelC1,ssSelC2);
      for (let r=rMin; r<=rMax; r++) {
        const srcRaw = ssData[r]?.[cMin]?.raw||'';
        for (let c=cMin+1; c<=cMax; c++) ssSetRaw(r, c, ssShiftFormula(srcRaw, 0, c-cMin));
      }
      ssRecomputeAll(); ssRenderBody(); ssHighlightSelection();
      ssSetStatus('→ Fill Right');
    }

    // Shift cell references in a formula by (dr, dc)
    function ssShiftFormula(raw, dr, dc) {
      if (!raw.startsWith('=')) return raw;
      // Replace cell refs like A1, B3 (not absolute $A$1)
      return raw.replace(/\$?([A-Ta-t])\$?(\d+)/g, (m, col, row) => {
        if (m.startsWith('$')) return m; // absolute
        const newC = SS_COLS.indexOf(col.toUpperCase()) + dc;
        const newR = parseInt(row) - 1 + dr;
        if (newC<0||newR<0||newC>=SS_COLS.length) return m;
        return SS_COLS[newC]+(newR+1);
      });
    }

    // ─── AUTOFILL DRAG (fill handle) ──────────────────────────────────────────
    function ssFillHandleDown(e) {
      e.preventDefault(); e.stopPropagation();
      ssFillDragging = true;
      ssFillStartR = ssSelR2; ssFillStartC = ssSelC2;
      document.addEventListener('mousemove', ssFillHandleMove);
      document.addEventListener('mouseup',   ssFillHandleUp);
    }
    function ssFillHandleMove(e) {
      if (!ssFillDragging) return;
      const el = document.elementFromPoint(e.clientX, e.clientY);
      if (!el) return;
      const td = el.closest('.ss-cell');
      if (!td) return;
      const r=+td.dataset.r, c=+td.dataset.c;
      ssSelR2=r; ssSelC2=c;
      ssHighlightSelection();
    }
    function ssFillHandleUp() {
      if (!ssFillDragging) return;
      ssFillDragging=false;
      document.removeEventListener('mousemove', ssFillHandleMove);
      document.removeEventListener('mouseup',   ssFillHandleUp);
      // Fill from anchor
      ssSaveUndo();
      const r0=ssFillStartR, c0=ssFillStartC;
      const rEnd=ssSelR2, cEnd=ssSelC2;
      const srcRaw = ssData[r0]?.[c0]?.raw||'';
      if (rEnd!==r0) {
        const step = rEnd>r0?1:-1;
        for (let r=r0+step; r!==rEnd+step; r+=step) ssSetRaw(r, c0, ssShiftFormula(srcRaw, r-r0, 0));
      } else if (cEnd!==c0) {
        const step = cEnd>c0?1:-1;
        for (let c=c0+step; c!==cEnd+step; c+=step) ssSetRaw(r0, c, ssShiftFormula(srcRaw, 0, c-c0));
      }
      ssRecomputeAll(); ssRenderBody(); ssHighlightSelection();
      ssSetStatus('⚡ AutoFill xong');
    }

    // ─── COLUMN RESIZE ────────────────────────────────────────────────────────
    function ssResizeStart(e, col) {
      e.preventDefault(); e.stopPropagation();
      ssResizingCol = col;
      ssResizeStartX = e.clientX;
      ssResizeStartW = ssColWidths[col];
      document.addEventListener('mousemove', ssResizeMove);
      document.addEventListener('mouseup',   ssResizeEnd);
    }
    function ssResizeMove(e) {
      if (ssResizingCol<0) return;
      const dx = e.clientX - ssResizeStartX;
      ssColWidths[ssResizingCol] = Math.max(30, ssResizeStartW + dx);
      // Update th width live
      const th = document.querySelector(`.ss-col-header[data-col="${ssResizingCol}"]`);
      if (th) { th.style.width=ssColWidths[ssResizingCol]+'px'; th.style.minWidth=ssColWidths[ssResizingCol]+'px'; }
      document.querySelectorAll(`.ss-cell[data-c="${ssResizingCol}"]`).forEach(td=>{
        td.style.width=ssColWidths[ssResizingCol]+'px'; td.style.maxWidth=ssColWidths[ssResizingCol]+'px';
      });
    }
    function ssResizeEnd() {
      ssResizingCol=-1;
      document.removeEventListener('mousemove', ssResizeMove);
      document.removeEventListener('mouseup',   ssResizeEnd);
    }

    // ─── INSERT / DELETE ROW & COL ────────────────────────────────────────────
    function ssInsertRowAbove() {
      ssSaveUndo();
      const r=Math.min(ssSelR1,ssSelR2);
      const newRow = Array.from({length:ssCols},()=>({raw:'',value:'',fmt:'general',bold:false,italic:false,color:'',bg:''}));
      ssData.splice(r, 0, newRow);
      ssRows++;
      // Update formulas: shift all refs at or below r
      ssShiftAllFormulas(r, 0, 1, 0);
      ssRecomputeAll(); ssRenderBody(); ssHighlightSelection();
      ssSetStatus(`➕ Đã chèn hàng tại ${r+1}`);
    }
    function ssInsertRowBelow() {
      ssSaveUndo();
      const r=Math.max(ssSelR1,ssSelR2)+1;
      const newRow = Array.from({length:ssCols},()=>({raw:'',value:'',fmt:'general',bold:false,italic:false,color:'',bg:''}));
      ssData.splice(r, 0, newRow);
      ssRows++;
      ssShiftAllFormulas(r, 0, 1, 0);
      ssRecomputeAll(); ssRenderBody(); ssHighlightSelection();
      ssSetStatus(`➕ Đã chèn hàng tại ${r+1}`);
    }
    function ssDeleteRows() {
      const rMin=Math.min(ssSelR1,ssSelR2), rMax=Math.max(ssSelR1,ssSelR2);
      if (ssRows-(rMax-rMin+1)<1) return ssSetStatus('❌ Không thể xóa hết hàng');
      ssSaveUndo();
      ssData.splice(rMin, rMax-rMin+1);
      ssRows = ssData.length;
      ssShiftAllFormulas(rMin, 0, -(rMax-rMin+1), 0);
      ssSelR1=ssSelR2=Math.min(rMin,ssRows-1); ssSelC1=ssSelC2=ssSelC1;
      ssRecomputeAll(); ssRenderBody(); ssHighlightSelection();
      ssSetStatus(`🗑️ Đã xóa ${rMax-rMin+1} hàng`);
    }
    function ssInsertColLeft() {
      ssSaveUndo();
      const c=Math.min(ssSelC1,ssSelC2);
      ssData.forEach(row => row.splice(c, 0, {raw:'',value:'',fmt:'general',bold:false,italic:false,color:'',bg:''}));
      ssCols++;
      ssColWidths.splice(c, 0, 90);
      ssShiftAllFormulas(0, c, 0, 1);
      ssRecomputeAll(); ssRender(); ssHighlightSelection();
    }
    function ssInsertColRight() {
      ssSaveUndo();
      const c=Math.max(ssSelC1,ssSelC2)+1;
      ssData.forEach(row => row.splice(c, 0, {raw:'',value:'',fmt:'general',bold:false,italic:false,color:'',bg:''}));
      ssCols++;
      ssColWidths.splice(c, 0, 90);
      ssShiftAllFormulas(0, c, 0, 1);
      ssRecomputeAll(); ssRender(); ssHighlightSelection();
    }
    function ssDeleteCols() {
      const cMin=Math.min(ssSelC1,ssSelC2), cMax=Math.max(ssSelC1,ssSelC2);
      if (ssCols-(cMax-cMin+1)<1) return ssSetStatus('❌ Không thể xóa hết cột');
      ssSaveUndo();
      ssData.forEach(row => row.splice(cMin, cMax-cMin+1));
      ssCols -= (cMax-cMin+1);
      ssColWidths.splice(cMin, cMax-cMin+1);
      ssShiftAllFormulas(0, cMin, 0, -(cMax-cMin+1));
      ssSelC1=ssSelC2=Math.min(cMin,ssCols-1);
      ssRecomputeAll(); ssRender(); ssHighlightSelection();
    }

    function ssShiftAllFormulas(fromR, fromC, dR, dC) {
      // Shift all formula cell references
      for (let r=0; r<ssData.length; r++)
        for (let c=0; c<(ssData[r]?.length||0); c++) {
          const raw = ssData[r]?.[c]?.raw||'';
          if (!raw.startsWith('=')) continue;
          ssData[r][c].raw = raw.replace(/\$?([A-Ta-t])\$?(\d+)/g, (m, col, row) => {
            if (m.includes('$')) return m;
            let ci = SS_COLS.indexOf(col.toUpperCase());
            let ri = parseInt(row)-1;
            if (dR!==0 && ri>=fromR) ri+=dR;
            if (dC!==0 && ci>=fromC) ci+=dC;
            if (ri<0||ci<0||ci>=SS_COLS.length) return '#REF!';
            return SS_COLS[ci]+(ri+1);
          });
        }
    }

    // ─── FORMATTING ───────────────────────────────────────────────────────────
    function ssApplyFmt(selection_fn) {
      ssSaveUndo();
      const rMin=Math.min(ssSelR1,ssSelR2), rMax=Math.max(ssSelR1,ssSelR2);
      const cMin=Math.min(ssSelC1,ssSelC2), cMax=Math.max(ssSelC1,ssSelC2);
      for (let r=rMin;r<=rMax;r++) for (let c=cMin;c<=cMax;c++) if(ssData[r]?.[c]) selection_fn(ssData[r][c]);
      ssRenderBody(); ssHighlightSelection();
    }
    function ssToggleBold()      { ssApplyFmt(cell => cell.bold=!cell.bold); ssUpdateRibbonState(); }
    function ssToggleItalic()    { ssApplyFmt(cell => cell.italic=!cell.italic); ssUpdateRibbonState(); }
    function ssToggleUnderline() { ssApplyFmt(cell => cell.underline=!cell.underline); ssUpdateRibbonState(); }
    function ssSetFmt(fmt)       { ssApplyFmt(cell => cell.fmt=fmt); }
    function ssSetColor(color)   { ssApplyFmt(cell => cell.color=color); }
    function ssSetBg(color)      { ssApplyFmt(cell => cell.bg=color); }
    function ssSetAlign(align)   { ssApplyFmt(cell => cell.align=align); }
    function ssToggleWrap()      { ssApplyFmt(cell => cell.wrap=!cell.wrap); }
    function ssClearFormat()     { ssApplyFmt(cell => { cell.bold=false; cell.italic=false; cell.underline=false; cell.color=''; cell.bg=''; cell.fmt='general'; cell.align=''; cell.wrap=false; }); ssUpdateRibbonState(); }

    function ssUpdateRibbonState() {
      const cell = ssData[ssSelR2]?.[ssSelC2];
      if (!cell) return;
      const boldBtn = document.getElementById('ss-btn-bold');
      const italicBtn = document.getElementById('ss-btn-italic');
      const ulBtn = document.getElementById('ss-btn-underline');
      if (boldBtn)   boldBtn.classList.toggle('ss-rb-active', !!cell.bold);
      if (italicBtn) italicBtn.classList.toggle('ss-rb-active', !!cell.italic);
      if (ulBtn)     ulBtn.classList.toggle('ss-rb-active', !!cell.underline);
    }

    function ssFormatDisplay(val, fmt) {
      if (val==='' || val===null || val===undefined) return '';
      const n = parseFloat(val);
      const isN = !isNaN(n) && val!==true && val!==false;
      switch(fmt) {
        case 'number':   return isN ? n.toLocaleString('vi-VN',{minimumFractionDigits:2,maximumFractionDigits:2}) : val;
        case 'integer':  return isN ? n.toLocaleString('vi-VN',{maximumFractionDigits:0}) : val;
        case 'currency': return isN ? n.toLocaleString('vi-VN',{minimumFractionDigits:0,maximumFractionDigits:0})+' ₫' : val;
        case 'percent':  return isN ? (n*100).toFixed(2)+'%' : val;
        case 'date':     { try { const d=new Date(val); return `${d.getDate().toString().padStart(2,'0')}/${(d.getMonth()+1).toString().padStart(2,'0')}/${d.getFullYear()}`; } catch(e){return val;} }
        case 'scientific': return isN ? n.toExponential(2) : val;
        case 'text':     return String(val);
        default:         return String(val===true?'TRUE':val===false?'FALSE':val);
      }
    }

    // ─── AGGREGATE STATUS BAR ─────────────────────────────────────────────────
    function ssUpdateAggregate() {
      const agg = document.getElementById('ss-aggregate');
      if (!agg) return;
      const rMin=Math.min(ssSelR1,ssSelR2), rMax=Math.max(ssSelR1,ssSelR2);
      const cMin=Math.min(ssSelC1,ssSelC2), cMax=Math.max(ssSelC1,ssSelC2);
      const vals=[];
      for (let r=rMin;r<=rMax;r++) for(let c=cMin;c<=cMax;c++){
        const v=parseFloat(ssData[r]?.[c]?.value??ssData[r]?.[c]?.raw);
        if(!isNaN(v)) vals.push(v);
      }
      if (!vals.length) { agg.innerHTML=''; return; }
      const sum=vals.reduce((s,v)=>s+v,0), avg=sum/vals.length;
      agg.innerHTML=`<span>Đếm: <b>${vals.length}</b></span><span>Tổng: <b>${sum.toLocaleString('vi-VN',{maximumFractionDigits:4})}</b></span><span>TB: <b>${avg.toLocaleString('vi-VN',{maximumFractionDigits:4})}</b></span>`;
    }

    function ssSetStatus(msg) {
      const el=document.getElementById('ss-status'); if(el) el.textContent=msg;
    }

    // ─── CONTEXT MENU ─────────────────────────────────────────────────────────
    function ssShowContextMenu(e) {
      e.preventDefault();
      const td = e.currentTarget;
      const r=+td.dataset.r, c=+td.dataset.c;
      // Make sure this cell is in selection
      if (r<Math.min(ssSelR1,ssSelR2)||r>Math.max(ssSelR1,ssSelR2)||c<Math.min(ssSelC1,ssSelC2)||c>Math.max(ssSelC1,ssSelC2)) {
        ssFocusCell(r,c);
      }
      let menu = document.getElementById('ss-context-menu');
      if (!menu) { menu=document.createElement('div'); menu.id='ss-context-menu'; document.body.appendChild(menu); }
      menu.innerHTML=`
        <div class="ss-menu-item" onclick="ssCopyToClipboard();ssCloseMenu()">📋 Copy (Ctrl+C)</div>
        <div class="ss-menu-item" onclick="ssCutToClipboard();ssCloseMenu()">✂️ Cắt (Ctrl+X)</div>
        <div class="ss-menu-item" onclick="ssPasteFromClipboard();ssCloseMenu()">📌 Dán (Ctrl+V)</div>
        <div class="ss-menu-sep"></div>
        <div class="ss-menu-item" onclick="ssInsertRowAbove();ssCloseMenu()">➕ Chèn hàng phía trên</div>
        <div class="ss-menu-item" onclick="ssInsertRowBelow();ssCloseMenu()">➕ Chèn hàng phía dưới</div>
        <div class="ss-menu-item" onclick="ssDeleteRows();ssCloseMenu()">🗑️ Xóa hàng</div>
        <div class="ss-menu-sep"></div>
        <div class="ss-menu-item" onclick="ssInsertColLeft();ssCloseMenu()">➕ Chèn cột trái</div>
        <div class="ss-menu-item" onclick="ssInsertColRight();ssCloseMenu()">➕ Chèn cột phải</div>
        <div class="ss-menu-item" onclick="ssDeleteCols();ssCloseMenu()">🗑️ Xóa cột</div>
        <div class="ss-menu-sep"></div>
        <div class="ss-menu-item" onclick="ssDeleteSelection();ssCloseMenu()">❌ Xóa nội dung</div>
        <div class="ss-menu-sep"></div>
        <div class="ss-menu-item ss-menu-submenu">🎨 Định dạng ▶
          <div class="ss-submenu">
            <div class="ss-menu-item" onclick="ssSetFmt('general');ssCloseMenu()">Chung</div>
            <div class="ss-menu-item" onclick="ssSetFmt('number');ssCloseMenu()">Số (1.234,56)</div>
            <div class="ss-menu-item" onclick="ssSetFmt('integer');ssCloseMenu()">Số nguyên (1.234)</div>
            <div class="ss-menu-item" onclick="ssSetFmt('currency');ssCloseMenu()">Tiền tệ (₫)</div>
            <div class="ss-menu-item" onclick="ssSetFmt('percent');ssCloseMenu()">Phần trăm (%)</div>
            <div class="ss-menu-item" onclick="ssSetFmt('date');ssCloseMenu()">Ngày (dd/mm/yyyy)</div>
            <div class="ss-menu-item" onclick="ssSetFmt('text');ssCloseMenu()">Văn bản</div>
          </div>
        </div>
      `;
      menu.style.cssText=`position:fixed;top:${e.clientY}px;left:${e.clientX}px;z-index:9999;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:4px 0;min-width:200px;box-shadow:0 8px 32px rgba(0,0,0,0.4);`;
      setTimeout(()=>document.addEventListener('click',ssCloseMenu,{once:true}),0);
    }
    function ssCloseMenu() {
      const m=document.getElementById('ss-context-menu'); if(m) m.remove();
    }

    // ─── FORMULA ENGINE ───────────────────────────────────────────────────────
    function ssEvalFormula(expr, curR, curC, depth=0) {
      if (depth>12) return '#CIRC!';
      try { return _ssEval(expr.trim(), curR, curC, depth); }
      catch(e) { return '#ERR!'; }
    }

    function _ssEval(expr, curR, curC, depth) {
      expr = expr.trim();
      if (!expr) return '';
      if (expr.startsWith('"') && expr.endsWith('"')) return expr.slice(1,-1);
      if (/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(expr)) return parseFloat(expr);
      if (expr.toUpperCase()==='TRUE') return true;
      if (expr.toUpperCase()==='FALSE') return false;
      // Absolute/relative cell ref
      if (/^\$?[A-Ta-t]\$?\d+$/.test(expr)) return ssGetCellValue(expr.replace(/\$/g,''));
      // Paren wrap
      if (expr.startsWith('(') && ssMatchParen(expr)===expr.length-1)
        return _ssEval(expr.slice(1,-1), curR, curC, depth);
      // Function call
      const fnM = expr.match(/^([A-Z_][A-Z0-9_.]*)\s*\((.*)\)$/is);
      if (fnM) return ssCallFn(fnM[1].toUpperCase(), ssSplitArgs(fnM[2]), curR, curC, depth);
      // Binary ops (precedence: & < comparisons < +- < */ < ^)
      for (const ops of [['&'],['>=','<=','<>','!=','>','<','='],['+','-'],['*','/'],['^']]) {
        const res = ssSplitOnOp(expr, ops, curR, curC, depth);
        if (res!==null) return res;
      }
      if (expr.startsWith('-')) {
        const v=_ssEval(expr.slice(1),curR,curC,depth);
        return typeof v==='number'?-v:'#VALUE!';
      }
      throw new Error('unknown: '+expr);
    }

    function ssGetCellValue(ref) {
      const m = ref.toUpperCase().match(/^([A-T])(\d+)$/);
      if (!m) return '#REF!';
      const c=SS_COLS.indexOf(m[1]), r=+m[2]-1;
      if (c<0||r<0||r>=ssRows||c>=ssCols) return '#REF!';
      const cell=ssData[r][c];
      const v=cell.value!==''?cell.value:cell.raw;
      const n=parseFloat(v);
      return isNaN(n)?v:n;
    }

    function ssGetRange(rangeStr) {
      const m=rangeStr.toUpperCase().match(/^([A-T])(\d+):([A-T])(\d+)$/);
      if (!m) return [];
      const c1=SS_COLS.indexOf(m[1]),r1=+m[2]-1,c2=SS_COLS.indexOf(m[3]),r2=+m[4]-1;
      const vals=[];
      for(let r=Math.min(r1,r2);r<=Math.max(r1,r2);r++)
        for(let c=Math.min(c1,c2);c<=Math.max(c1,c2);c++) {
          const cell=ssData[r]?.[c]; const v=cell?.value!==''?cell?.value:cell?.raw;
          const n=parseFloat(v); vals.push(isNaN(n)?v:n);
        }
      return vals;
    }
    function ssGetRangeRaw(rangeStr) {
      const m=rangeStr.toUpperCase().match(/^([A-T])(\d+):([A-T])(\d+)$/);
      if (!m) return [];
      const c1=SS_COLS.indexOf(m[1]),r1=+m[2]-1,c2=SS_COLS.indexOf(m[3]),r2=+m[4]-1;
      const vals=[];
      for(let r=Math.min(r1,r2);r<=Math.max(r1,r2);r++)
        for(let c=Math.min(c1,c2);c<=Math.max(c1,c2);c++) {
          const cell=ssData[r]?.[c]; vals.push(cell?.value!==''?cell?.value:(cell?.raw??''));
        }
      return vals;
    }

    function ssMatchParen(str) {
      let d=0;
      for(let i=0;i<str.length;i++){
        if(str[i]==='(')d++;
        else if(str[i]===')'){d--;if(d===0)return i;}
        else if(str[i]==='"'){i=str.indexOf('"',i+1);if(i===-1)return -1;}
      }
      return -1;
    }

    function ssSplitArgs(str) {
      const args=[]; let d=0,cur='',inStr=false;
      for(let i=0;i<str.length;i++){
        const ch=str[i];
        if(ch==='"'&&!inStr)inStr=true;
        else if(ch==='"'&&inStr)inStr=false;
        else if(!inStr){
          if(ch==='('||ch==='[')d++;
          else if(ch===')'||ch===']')d--;
          else if(ch===','&&d===0){args.push(cur);cur='';continue;}
        }
        cur+=ch;
      }
      if(cur||args.length)args.push(cur);
      return args;
    }

    function ssSplitOnOp(expr, ops, curR, curC, depth) {
      let pD=0, inStr=false;
      for(let i=expr.length-1;i>=0;i--){
        const ch=expr[i];
        if(ch==='"')inStr=!inStr;
        if(inStr)continue;
        if(ch===')'||ch===']')pD++;
        else if(ch==='('||ch==='[')pD--;
        if(pD>0)continue;
        for(const op of ops){
          if(expr.slice(i,i+op.length)===op){
            const left=expr.slice(0,i).trim(), right=expr.slice(i+op.length).trim();
            if(!left)continue;
            const L=_ssEval(left,curR,curC,depth+1), R=_ssEval(right,curR,curC,depth+1);
            if(op==='&')return String(L===undefined?'':L)+String(R===undefined?'':R);
            if(op==='+')return(parseFloat(L)||0)+(parseFloat(R)||0);
            if(op==='-')return(parseFloat(L)||0)-(parseFloat(R)||0);
            if(op==='*')return(parseFloat(L)||0)*(parseFloat(R)||0);
            if(op==='/'){const d=parseFloat(R);return d===0?'#DIV/0!':(parseFloat(L)||0)/d;}
            if(op==='^')return Math.pow(parseFloat(L)||0,parseFloat(R)||0);
            if(op==='=')return String(L)===String(R)||L==R;
            if(op==='<>')return String(L)!==String(R)&&L!=R;
            if(op==='!=')return L!=R;
            if(op==='>=')return parseFloat(L)>=parseFloat(R);
            if(op==='<=')return parseFloat(L)<=parseFloat(R);
            if(op==='>') return parseFloat(L)>parseFloat(R);
            if(op==='<') return parseFloat(L)<parseFloat(R);
          }
        }
      }
      return null;
    }

    function ssMatchCriteria(val, crit) {
      if (typeof crit==='string') {
        if (crit.startsWith('>=')) return parseFloat(val)>=parseFloat(crit.slice(2));
        if (crit.startsWith('<=')) return parseFloat(val)<=parseFloat(crit.slice(2));
        if (crit.startsWith('<>')) return String(val)!==crit.slice(2);
        if (crit.startsWith('>'))  return parseFloat(val)>parseFloat(crit.slice(1));
        if (crit.startsWith('<'))  return parseFloat(val)<parseFloat(crit.slice(1));
        // Wildcard
        const pat='^'+crit.replace(/[.+^${}()|[\]\\]/g,'\\$&').replace(/\*/g,'.*').replace(/\?/g,'.')+'$';
        return new RegExp(pat,'i').test(String(val));
      }
      return val==crit || parseFloat(val)===parseFloat(crit);
    }

    function ssCallFn(name, args, curR, curC, depth) {
      const ev  = a => _ssEval(a.trim(), curR, curC, depth+1);
      const evN = a => parseFloat(ev(a))||0;
      const gr  = a => /^[A-T]\d+:[A-T]\d+$/i.test(a.trim()) ? ssGetRange(a.trim()) : [ev(a)];
      const grR = a => /^[A-T]\d+:[A-T]\d+$/i.test(a.trim()) ? ssGetRangeRaw(a.trim()) : [ev(a)];
      const nums = args.flatMap(gr).map(v=>parseFloat(v)).filter(n=>!isNaN(n));

      switch(name) {
        // ── Math & Stats ──────────────────────────────────────────────
        case 'SUM':       return args.flatMap(gr).reduce((s,v)=>s+(parseFloat(v)||0),0);
        case 'PRODUCT':   return args.flatMap(gr).reduce((p,v)=>p*(parseFloat(v)||1),1);
        case 'AVERAGE':   { const n=nums; return n.length?n.reduce((s,v)=>s+v,0)/n.length:'#DIV/0!'; }
        case 'MEAN':      { const n=nums; return n.length?n.reduce((s,v)=>s+v,0)/n.length:'#DIV/0!'; }
        case 'MIN':       return nums.length?Math.min(...nums):0;
        case 'MAX':       return nums.length?Math.max(...nums):0;
        case 'COUNT':     return args.flatMap(gr).filter(v=>!isNaN(parseFloat(v))).length;
        case 'COUNTA':    return args.flatMap(grR).filter(v=>v!==''&&v!==null&&v!==undefined).length;
        case 'COUNTBLANK':return args.flatMap(grR).filter(v=>v===''||v===null).length;
        case 'ABS':       return Math.abs(evN(args[0]));
        case 'INT':       return Math.trunc(evN(args[0]));
        case 'TRUNC':     { const v=evN(args[0]),d=args[1]?parseInt(ev(args[1])):0; const m=Math.pow(10,d); return Math.trunc(v*m)/m; }
        case 'ROUND':     { const v=evN(args[0]),d=args[1]?parseInt(ev(args[1])):0; return parseFloat(v.toFixed(Math.max(0,d))); }
        case 'ROUNDUP':   { const v=evN(args[0]),d=args[1]?parseInt(ev(args[1])):0; const m=Math.pow(10,d); return Math.ceil(v*m)/m; }
        case 'ROUNDDOWN': { const v=evN(args[0]),d=args[1]?parseInt(ev(args[1])):0; const m=Math.pow(10,d); return Math.floor(v*m)/m; }
        case 'CEILING':   { const v=evN(args[0]),s=args[1]?evN(args[1]):1; return s===0?0:Math.ceil(v/s)*s; }
        case 'FLOOR':     { const v=evN(args[0]),s=args[1]?evN(args[1]):1; return s===0?0:Math.floor(v/s)*s; }
        case 'SQRT':      { const v=evN(args[0]); return v<0?'#NUM!':Math.sqrt(v); }
        case 'POWER':     return Math.pow(evN(args[0]),evN(args[1]));
        case 'MOD':       { const a=evN(args[0]),b=evN(args[1]); return b===0?'#DIV/0!':a%b; }
        case 'LOG':       { const v=evN(args[0]),base=args[1]?evN(args[1]):10; return Math.log(v)/Math.log(base); }
        case 'LOG10':     return Math.log10(evN(args[0]));
        case 'LN':        return Math.log(evN(args[0]));
        case 'EXP':       return Math.exp(evN(args[0]));
        case 'PI':        return Math.PI;
        case 'RAND':      return Math.random();
        case 'RANDBETWEEN':{ const lo=evN(args[0]),hi=evN(args[1]); return Math.floor(lo+Math.random()*(hi-lo+1)); }
        case 'SIGN':      { const v=evN(args[0]); return v>0?1:v<0?-1:0; }
        case 'FACT':      { let n=Math.trunc(evN(args[0])),f=1; while(n>1)f*=n--; return f; }
        case 'SUMPRODUCT':{ const ranges=args.map(a=>/^[A-T]\d+:[A-T]\d+$/i.test(a.trim())?ssGetRangeRaw(a.trim()):[ev(a)]); const len=Math.min(...ranges.map(r=>r.length)); let s=0; for(let i=0;i<len;i++) s+=ranges.reduce((p,r)=>p*(parseFloat(r[i])||0),1); return s; }
        case 'SUMIF':     { const rv=gr(args[0]),crit=ev(args[1]),sv=args[2]?gr(args[2]):rv; return rv.reduce((s,v,i)=>ssMatchCriteria(v,crit)?s+(parseFloat(sv[i])||0):s,0); }
        case 'SUMIFS':    { const sv=gr(args[0]); let mask=sv.map(()=>true); for(let i=1;i<args.length-1;i+=2){const rv2=gr(args[i]),crit2=ev(args[i+1]); rv2.forEach((v,j)=>{if(!ssMatchCriteria(v,crit2))mask[j]=false;});} return sv.reduce((s,v,i)=>mask[i]?s+(parseFloat(v)||0):s,0); }
        case 'COUNTIF':   { const rv=gr(args[0]),crit=ev(args[1]); return rv.filter(v=>ssMatchCriteria(v,crit)).length; }
        case 'COUNTIFS':  { const rv=gr(args[0]),crit=ev(args[1]); let cnt=rv.filter(v=>ssMatchCriteria(v,crit)).length; return cnt; }
        case 'AVERAGEIF': { const rv=gr(args[0]),crit=ev(args[1]),av=args[2]?gr(args[2]):rv; const m=rv.map((v,i)=>ssMatchCriteria(v,crit)?parseFloat(av[i]):NaN).filter(n=>!isNaN(n)); return m.length?m.reduce((s,v)=>s+v,0)/m.length:'#DIV/0!'; }
        case 'LARGE':     { const arr=[...nums].sort((a,b)=>b-a),k=parseInt(ev(args[args.length>1?1:0])); return arr[k-1]??'#NUM!'; }
        case 'SMALL':     { const arr=[...nums].sort((a,b)=>a-b),k=parseInt(ev(args[args.length>1?1:0])); return arr[k-1]??'#NUM!'; }
        case 'MEDIAN':    { const s=[...nums].sort((a,b)=>a-b),m=Math.floor(s.length/2); return s.length%2?s[m]:(s[m-1]+s[m])/2; }
        case 'MODE':      { const freq={}; nums.forEach(v=>{freq[v]=(freq[v]||0)+1;}); let best=null,bv=0; for(const k in freq)if(freq[k]>bv){bv=freq[k];best=parseFloat(k);} return best??'#N/A'; }
        case 'STDEV':     { const n=nums,mean=n.reduce((s,v)=>s+v,0)/n.length; return Math.sqrt(n.reduce((s,v)=>s+(v-mean)**2,0)/(n.length-1)); }
        case 'STDEVP':    { const n=nums,mean=n.reduce((s,v)=>s+v,0)/n.length; return Math.sqrt(n.reduce((s,v)=>s+(v-mean)**2,0)/n.length); }
        case 'VAR':       { const n=nums,mean=n.reduce((s,v)=>s+v,0)/n.length; return n.reduce((s,v)=>s+(v-mean)**2,0)/(n.length-1); }
        case 'GCD':       { const g=(a,b)=>b?g(b,a%b):a; return args.flatMap(gr).map(v=>Math.abs(parseInt(v))).reduce((a,b)=>g(a,b)); }
        case 'LCM':       { const g=(a,b)=>b?g(b,a%b):a; return args.flatMap(gr).map(v=>Math.abs(parseInt(v))).reduce((a,b)=>a/g(a,b)*b); }

        // ── Logic ─────────────────────────────────────────────────────
        case 'IF':      { const cond=ev(args[0]); return(cond&&cond!=='FALSE'&&cond!==0&&cond!=='0')?ev(args[1]||'""'):ev(args[2]||'""'); }
        case 'IFS':     { for(let i=0;i<args.length-1;i+=2){const c=ev(args[i]);if(c&&c!=='FALSE'&&c!==0)return ev(args[i+1]);} return '#N/A'; }
        case 'IFERROR': { try{const v=ev(args[0]);return String(v).startsWith('#')?ev(args[1]):v;}catch(e){return ev(args[1]);} }
        case 'IFNA':    { try{const v=ev(args[0]);return v==='#N/A'?ev(args[1]):v;}catch(e){return ev(args[1]);} }
        case 'AND':     return args.every(a=>{const v=ev(a);return v&&v!=='FALSE'&&v!==0;});
        case 'OR':      return args.some(a=>{const v=ev(a);return v&&v!=='FALSE'&&v!==0;});
        case 'NOT':     { const v=ev(args[0]); return!(v&&v!=='FALSE'&&v!==0); }
        case 'XOR':     return args.filter(a=>{const v=ev(a);return v&&v!=='FALSE'&&v!==0;}).length%2===1;
        case 'TRUE':    return true;
        case 'FALSE':   return false;
        case 'SWITCH':  { const base=ev(args[0]); for(let i=1;i<args.length-1;i+=2){if(String(ev(args[i]))===String(base))return ev(args[i+1]);} return args.length%2===0?ev(args[args.length-1]):'#N/A'; }

        // ── Type checks ───────────────────────────────────────────────
        case 'ISNUMBER': return !isNaN(parseFloat(ev(args[0])));
        case 'ISTEXT':   { const v=ev(args[0]); return typeof v==='string'&&isNaN(parseFloat(v)); }
        case 'ISBLANK':  { const v=ev(args[0]); return v===''||v===null||v===undefined; }
        case 'ISERROR':  return String(ev(args[0])).startsWith('#');
        case 'ISNA':     return ev(args[0])==='#N/A';

        // ── Text ──────────────────────────────────────────────────────
        case 'LEN':         return String(ev(args[0])).length;
        case 'LEFT':        { const s=String(ev(args[0])),n=args[1]?parseInt(ev(args[1])):1; return s.slice(0,n); }
        case 'RIGHT':       { const s=String(ev(args[0])),n=args[1]?parseInt(ev(args[1])):1; return s.slice(-n); }
        case 'MID':         { const s=String(ev(args[0])),st=parseInt(ev(args[1]))-1,n=parseInt(ev(args[2])); return s.slice(st,st+n); }
        case 'UPPER':       return String(ev(args[0])).toUpperCase();
        case 'LOWER':       return String(ev(args[0])).toLowerCase();
        case 'PROPER':      return String(ev(args[0])).replace(/\b\w/g,c=>c.toUpperCase());
        case 'TRIM':        return String(ev(args[0])).trim().replace(/\s+/g,' ');
        case 'LTRIM':       return String(ev(args[0])).trimStart();
        case 'RTRIM':       return String(ev(args[0])).trimEnd();
        case 'CONCATENATE':
        case 'CONCAT':      return args.map(a=>String(ev(a))).join('');
        case 'TEXTJOIN':    { const delim=String(ev(args[0])),ig=ev(args[1]); const vals=args.slice(2).flatMap(a=>/^[A-T]\d+:[A-T]\d+$/i.test(a.trim())?gr(a):[ev(a)]); return(ig?vals.filter(v=>v!==''):vals).join(delim); }
        case 'REPT':        return String(ev(args[0])).repeat(parseInt(ev(args[1]))||0);
        case 'SUBSTITUTE':  { const s=String(ev(args[0])),old=String(ev(args[1])),rep=String(ev(args[2])); return s.split(old).join(rep); }
        case 'REPLACE':     { const s=String(ev(args[0])),st=parseInt(ev(args[1]))-1,n=parseInt(ev(args[2])),rep=String(ev(args[3])); return s.slice(0,st)+rep+s.slice(st+n); }
        case 'FIND':        { const f=String(ev(args[0])),s=String(ev(args[1])),st=args[2]?parseInt(ev(args[2]))-1:0; const i=s.indexOf(f,st); return i===-1?'#VALUE!':i+1; }
        case 'SEARCH':      { const f=String(ev(args[0])).toLowerCase(),s=String(ev(args[1])).toLowerCase(); const i=s.indexOf(f); return i===-1?'#VALUE!':i+1; }
        case 'TEXT':        { const v=parseFloat(ev(args[0])),fmt=String(ev(args[1])); if(fmt.includes('#,'))return v.toLocaleString('vi-VN'); if(fmt.includes('0%'))return(v*100).toFixed(2)+'%'; return v.toFixed((fmt.match(/\.(0+)/)||['',''])[1].length); }
        case 'VALUE':       { const v=parseFloat(String(ev(args[0])).replace(/[,\s]/g,'')); return isNaN(v)?'#VALUE!':v; }
        case 'CHAR':        return String.fromCharCode(parseInt(ev(args[0])));
        case 'CODE':        return String(ev(args[0])).charCodeAt(0);
        case 'EXACT':       return String(ev(args[0]))===String(ev(args[1]));
        case 'NUMBERVALUE': { const v=parseFloat(String(ev(args[0])).replace(/\./g,'').replace(',','.')); return isNaN(v)?'#VALUE!':v; }

        // ── Date/Time ─────────────────────────────────────────────────
        case 'TODAY':    { const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
        case 'NOW':      return new Date().toLocaleString('vi-VN');
        case 'YEAR':     return new Date(ev(args[0])).getFullYear();
        case 'MONTH':    return new Date(ev(args[0])).getMonth()+1;
        case 'DAY':      return new Date(ev(args[0])).getDate();
        case 'HOUR':     return new Date(ev(args[0])).getHours();
        case 'MINUTE':   return new Date(ev(args[0])).getMinutes();
        case 'SECOND':   return new Date(ev(args[0])).getSeconds();
        case 'DATE':     { const y=+ev(args[0]),mo=+ev(args[1]),d=+ev(args[2]); return `${y}-${String(mo).padStart(2,'0')}-${String(d).padStart(2,'0')}`; }
        case 'DATEDIF':  { const d1=new Date(ev(args[0])),d2=new Date(ev(args[1])),unit=String(ev(args[2])).toUpperCase(); if(unit==='D')return Math.floor((d2-d1)/86400000); if(unit==='M')return(d2.getFullYear()-d1.getFullYear())*12+(d2.getMonth()-d1.getMonth()); if(unit==='Y')return d2.getFullYear()-d1.getFullYear(); return '#VALUE!'; }
        case 'EDATE':    { const d=new Date(ev(args[0])); d.setMonth(d.getMonth()+parseInt(ev(args[1]))); return d.toISOString().slice(0,10); }
        case 'EOMONTH':  { const d=new Date(ev(args[0])); d.setMonth(d.getMonth()+parseInt(ev(args[1]))+1); d.setDate(0); return d.toISOString().slice(0,10); }
        case 'WEEKDAY':  return new Date(ev(args[0])).getDay()+1;
        case 'DAYS':     return Math.floor((new Date(ev(args[0]))-new Date(ev(args[1])))/86400000);
        case 'NETWORKDAYS': { let d1=new Date(ev(args[0])),d2=new Date(ev(args[1])),cnt=0; while(d1<=d2){const dw=d1.getDay();if(dw>0&&dw<6)cnt++;d1.setDate(d1.getDate()+1);} return cnt; }

        // ── Lookup ────────────────────────────────────────────────────
        case 'VLOOKUP': {
          const lookup=ev(args[0]);
          const m2=args[1].trim().toUpperCase().match(/^([A-T])(\d+):([A-T])(\d+)$/);
          if(!m2)return '#N/A';
          const c1=SS_COLS.indexOf(m2[1]),r1=+m2[2]-1,r2=+m2[4]-1;
          const colIdx=parseInt(ev(args[2]))-1;
          const exact=args[3]?String(ev(args[3])).toLowerCase()==='false'||ev(args[3])===0:false;
          for(let r=r1;r<=r2;r++){
            const key=ssData[r]?.[c1]?.raw;
            if(exact?String(key)===String(lookup):String(key).toLowerCase()===String(lookup).toLowerCase()){
              const tc=c1+colIdx;
              return ssData[r]?.[tc]?.value??ssData[r]?.[tc]?.raw??'#N/A';
            }
          }
          return '#N/A';
        }
        case 'HLOOKUP': {
          const lookup=ev(args[0]);
          const m2=args[1].trim().toUpperCase().match(/^([A-T])(\d+):([A-T])(\d+)$/);
          if(!m2)return '#N/A';
          const c1=SS_COLS.indexOf(m2[1]),r1=+m2[2]-1,c2=SS_COLS.indexOf(m2[3]);
          const rowIdx=parseInt(ev(args[2]))-1;
          const exact=args[3]?String(ev(args[3])).toLowerCase()==='false'||ev(args[3])===0:false;
          for(let c=c1;c<=c2;c++){
            const key=ssData[r1]?.[c]?.raw;
            if(exact?String(key)===String(lookup):String(key).toLowerCase()===String(lookup).toLowerCase()){
              const tr=r1+rowIdx;
              return ssData[tr]?.[c]?.value??ssData[tr]?.[c]?.raw??'#N/A';
            }
          }
          return '#N/A';
        }
        case 'INDEX': {
          const rangeM=args[0].trim().toUpperCase().match(/^([A-T])(\d+):([A-T])(\d+)$/);
          if(!rangeM)return '#REF!';
          const c1=SS_COLS.indexOf(rangeM[1]),r1=+rangeM[2]-1;
          const ri=parseInt(ev(args[1]))-1, ci=args[2]?parseInt(ev(args[2]))-1:0;
          const cell=ssData[r1+ri]?.[c1+ci];
          return cell?.value!==''?cell?.value:cell?.raw??'#REF!';
        }
        case 'MATCH': {
          const lookup=ev(args[0]);
          const rangeM=args[1].trim().toUpperCase().match(/^([A-T])(\d+):([A-T])(\d+)$/);
          if(!rangeM)return '#N/A';
          const c1=SS_COLS.indexOf(rangeM[1]),r1=+rangeM[2]-1,c2=SS_COLS.indexOf(rangeM[3]),r2=+rangeM[4]-1;
          const mType=args[2]?parseInt(ev(args[2])):1;
          for(let r=r1;r<=r2;r++)for(let c=c1;c<=c2;c++){
            const v=ssData[r]?.[c]?.raw;
            if(mType===0&&String(v).toLowerCase()===String(lookup).toLowerCase())return(r-r1)+(c-c1)+1;
            if(mType===1&&parseFloat(v)===parseFloat(lookup))return(r-r1)+(c-c1)+1;
          }
          return '#N/A';
        }
        case 'CHOOSE': { const idx=parseInt(ev(args[0]))-1; return idx>=0&&idx<args.length-1?ev(args[idx+1]):'#VALUE!'; }
        case 'INDIRECT': {
          const ref=String(ev(args[0]));
          if(/^[A-T]\d+$/i.test(ref)) return ssGetCellValue(ref);
          if(/^[A-T]\d+:[A-T]\d+$/i.test(ref)) return ssGetRange(ref);
          return '#REF!';
        }
        case 'OFFSET': {
          const m2=args[0].trim().toUpperCase().match(/^([A-T])(\d+)$/);
          if(!m2)return '#REF!';
          const c0=SS_COLS.indexOf(m2[1]),r0=+m2[2]-1;
          const dr=parseInt(ev(args[1])),dc=parseInt(ev(args[2]));
          return ssGetCellValue(SS_COLS[c0+dc]+(r0+dr+1));
        }
        case 'ROW':    return curR+1;
        case 'COLUMN': return curC+1;
        case 'ROWS':   { const m2=args[0].trim().match(/^[A-T](\d+):[A-T](\d+)$/i); return m2?+m2[2]-+m2[1]+1:1; }
        case 'COLUMNS':{ const m2=args[0].trim().match(/^([A-T])\d+:([A-T])\d+$/i); return m2?SS_COLS.indexOf(m2[2].toUpperCase())-SS_COLS.indexOf(m2[1].toUpperCase())+1:1; }

        // ── Financial ─────────────────────────────────────────────────
        case 'PMT': {
          const rate=evN(args[0]),nper=evN(args[1]),pv=evN(args[2]);
          if(rate===0)return -pv/nper;
          return -(pv*rate*Math.pow(1+rate,nper))/(Math.pow(1+rate,nper)-1);
        }
        case 'FV':  { const r=evN(args[0]),n=evN(args[1]),pmt=evN(args[2]),pv=args[3]?evN(args[3]):0; return pmt*(Math.pow(1+r,n)-1)/r-pv*Math.pow(1+r,n); }
        case 'PV':  { const r=evN(args[0]),n=evN(args[1]),pmt=evN(args[2]); return r===0?-pmt*n:(-pmt*(1-Math.pow(1+r,-n))/r); }
        case 'RATE':{ return '#UNSUPPORTED'; }
        case 'NPV': { const r=evN(args[0]),cashflows=args.slice(1).flatMap(gr).map(v=>parseFloat(v)); return cashflows.reduce((s,v,i)=>s+v/Math.pow(1+r,i+1),0); }

        default: return `#NAME?`;
      }
    }

    // ─── TOOLBAR ACTIONS ──────────────────────────────────────────────────────
    function ssAddRow() {
      ssSaveUndo();
      ssRows++;
      ssData.push(Array.from({length:ssCols},()=>({raw:'',value:'',fmt:'general',bold:false,italic:false,color:'',bg:''})));
      ssRenderBody(); ssHighlightSelection();
      ssFocusCell(ssRows-1, 0);
    }
    function ssClear() {
      if (!confirm('Xóa toàn bộ nội dung bảng?')) return;
      ssInit();
    }

    function ssFillSample() {
      ssSaveUndo();
      const sample = [
        ['SHL','Bulong M8x25','500','Cái','Thép CT3','Mạ đen','∅8x25','1200','Lô 1',''],
        ['SHL','Vòng đệm M8','500','Cái','Thép lò xo','Không xử lý','M8','350','',''],
        ['CIT','Ê cu M10','300','Cái','Thép 45','Mạ kẽm','M10','800','Ưu tiên',''],
        ['CIT','Chốt Ø12x60','200','Cái','Thép C45','Tôi','∅12x60','2500','',''],
        ['SHL','Tấm đế 200x300','100','Tấm','ST37','Phun cát','200x300x10','15000','',''],
        ['MTB','Trục bậc Ø30','50','Cái','Thép 40Cr','Tôi+Ram','∅30xL150','45000','',''],
        ['MTB','Bạc lót Ø25','100','Cái','Đồng thau','Không','∅25/∅20x30','8000','',''],
        ['CIT','Lò xo nén','400','Cái','Thép lò xo 65Mn','Không','∅12x80','1800','',''],
        ['','','=SUM(C2:C9)','','','','','=SUM(H2:H9)','Tổng',''],
        ['','','=AVERAGE(C2:C9)','','','','','=AVERAGE(H2:H9)','Trung bình',''],
      ];
      sample.forEach((row, ri) => {
        row.forEach((val, ci) => {
          if (ci < ssCols && ri < ssRows) ssSetRaw(ri, ci, val);
        });
      });
      ssRecomputeAll();
      ssRenderBody();
      ssHighlightSelection();
      ssSetStatus('⚡ Đã điền dữ liệu mẫu');
    }

    function ssGetTSV() {
      // Export with column headers as first row
      const headers = [];
      for (let c=0; c<ssCols; c++) headers.push(SS_COL_HEADERS[c]||SS_COLS[c]);
      const lines = [headers.join('\t')];
      for (let r=0; r<ssRows; r++) {
        const row = [];
        for (let c=0; c<ssCols; c++) {
          const cell = ssData[r]?.[c];
          row.push(cell?.raw||'');
        }
        if (row.some(v=>v!=='')) lines.push(row.join('\t'));
      }
      return lines.join('\r\n');
    }

    function ssExportToClipboard() {
      const tsv = ssGetTSV();
      navigator.clipboard.writeText(tsv).then(()=>ssSetStatus('📤 Đã copy toàn bộ bảng → Excel'));
    }

    function ssImportFromClipboard() {
      navigator.clipboard.readText().then(text=>{
        if(!text) return;
        ssLoadTSV(text);
        ssSetStatus('📥 Đã tải dữ liệu từ clipboard');
      }).catch(()=>ssSetStatus('❌ Không thể đọc clipboard'));
    }

    function ssLoadTSV(text) {
      ssSaveUndo();
      const lines = text.replace(/\r\n/g,'\n').replace(/\r/g,'\n').split('\n').filter(l=>l.trim());
      // Detect and skip header row if it matches SS_COL_HEADERS
      let startLine = 0;
      if (lines.length > 0) {
        const firstCells = lines[0].split('\t').map(s=>s.trim().toLowerCase());
        const isHeader = firstCells.some(c=>['khách hàng','tên chi tiết','số lượng','khach hang','ten chi tiet'].includes(c));
        if (isHeader) startLine = 1;
      }
      const dataLines = lines.slice(startLine);
      const maxCols = Math.max(...dataLines.map(l=>l.split('\t').length), ssCols);
      if (maxCols > ssCols) {
        ssData.forEach(row=>{ while(row.length<maxCols) row.push({raw:'',value:'',fmt:'general',bold:false,italic:false,color:'',bg:''}) });
        ssCols = maxCols;
        ssColWidths = [...ssColWidths, ...Array(maxCols-ssColWidths.length).fill(90)];
      }
      if (dataLines.length > ssRows) {
        while (ssData.length < dataLines.length) ssData.push(Array.from({length:ssCols},()=>({raw:'',value:'',fmt:'general',bold:false,italic:false,color:'',bg:''})));
        ssRows = ssData.length;
      }
      dataLines.forEach((line, ri) => {
        line.split('\t').forEach((val, ci) => {
          if (ri<ssRows && ci<ssCols) ssSetRaw(ri, ci, val);
        });
      });
      ssRecomputeAll(); ssRender(); ssHighlightSelection();
    }

    // ─── PREVIEW IMPORT ───────────────────────────────────────────────────────
    async function ssPreviewImport() {
      const tsv = ssGetTSV();
      const status = document.getElementById('ss-import-status');
      const wrap = document.getElementById('ss-preview-wrap');
      status.style.display='block';
      status.innerHTML='<span style="color:var(--accent);">Đang phân tích dữ liệu bảng tính...</span>';
      try {
        const res = await fetch('/api/v1/excel/paste-preview', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({tsv})
        });
        if (!res.ok) { const e=await res.json(); status.innerHTML=`<span style="color:var(--danger);">Lỗi: ${e.detail||'Không phân tích được'}</span>`; return; }
        const data = await res.json();
        ssLastPreviewItems = data.items||[];
        status.innerHTML=`<span style="color:var(--success);font-weight:700;">✅ Nhận diện ${data.total_items} chi tiết (Tổng SL: ${data.total_quantity}, KH: ${(data.companies||[]).join(', ')||'—'})</span>`;
        wrap.style.display='block';
        document.getElementById('ss-preview-tbody').innerHTML = ssLastPreviewItems.map(it=>`
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:7px 10px;">${it.row_index}</td>
            <td style="padding:7px 10px;"><b>${it.company||''}</b></td>
            <td style="padding:7px 10px;">${it.part_name||''}</td>
            <td style="padding:7px 10px;"><b style="color:var(--accent);">${it.quantity||''}</b></td>
            <td style="padding:7px 10px;">${it.unit||''}</td>
            <td style="padding:7px 10px;">${it.material||'—'}</td>
            <td style="padding:7px 10px;">${it.surface_treatment||'—'}</td>
            <td style="padding:7px 10px;">${it.size||'—'}</td>
            <td style="padding:7px 10px;">${it.price?it.price.toLocaleString('vi-VN')+' ₫':'—'}</td>
          </tr>`).join('');
      } catch(e) { status.innerHTML=`<span style="color:var(--danger);">Lỗi kết nối: ${e.message}</span>`; }
    }

    async function ssDoImport() {
      const tsv = ssGetTSV();
      const status = document.getElementById('ss-import-status');
      if (!confirm('Bạn có chắc muốn nạp toàn bộ dữ liệu bảng tính vào cơ sở dữ liệu và cấp mã QR không?')) return;
      status.style.display='block';
      status.innerHTML='<span style="color:var(--accent);">Đang nạp dữ liệu và cấp mã QR...</span>';
      try {
        const res = await fetch('/api/v1/excel/paste-import', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({tsv, po_prefix:'PO-SHEET'})
        });
        if (!res.ok) { const e=await res.json(); status.innerHTML=`<span style="color:var(--danger);">Lỗi: ${e.detail}</span>`; return; }
        const data = await res.json();
        status.innerHTML=`<span style="color:var(--success);font-weight:700;">🎉 Thành công: Đã tạo ${data.imported_products} sản phẩm và cấp ${data.imported_tracking_items} mã QR tracking!</span>`;
        setTimeout(()=>location.reload(), 2000);
      } catch(e) { status.innerHTML=`<span style="color:var(--danger);">Lỗi kết nối: ${e.message}</span>`; }
    }

    function ssCopyPreview() {
      if (!ssLastPreviewItems.length) return alert('Chưa có dữ liệu preview.');
      const headers=['Dòng','Khách Hàng','Tên Chi Tiết','Số Lượng','ĐVT','Vật Liệu','Xử Lý Bề Mặt','Kích Thước','Đơn Giá'];
      const lines=[headers.join('\t')];
      ssLastPreviewItems.forEach(it=>lines.push([it.row_index,it.company,it.part_name,it.quantity,it.unit,it.material||'',it.surface_treatment||'',it.size||'',it.price||''].join('\t')));
      navigator.clipboard.writeText(lines.join('\r\n')).then(()=>{
        const t=document.getElementById('toast');t.textContent='Đã copy bảng preview!';t.style.display='block';setTimeout(()=>t.style.display='none',2000);
      });
    }

    // ─── INIT ON LOAD ─────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => { ssInit(); });


"""


_SS_CSS = r"""

    /* ── Spreadsheet Engine Styles ──────────────────────────────────────── */
    #ss-container { user-select: none; }
    .ss-corner { width:36px; min-width:36px; background:var(--card-raised); border:1px solid var(--border); position:sticky; top:0; left:0; z-index:20; }
    .ss-col-header { background:var(--card-raised); border:1px solid var(--border); color:var(--text-muted); font-size:11px; font-weight:700; padding:0; position:sticky; top:0; z-index:10; white-space:nowrap; text-align:center; cursor:default; }
    .ss-col-header-inner { padding:5px 6px 3px; }
    .ss-col-sub { font-size:10px; color:var(--text-muted); opacity:0.65; font-weight:400; overflow:hidden; text-overflow:ellipsis; }
    .ss-col-resize { position:absolute; right:0; top:0; width:5px; height:100%; cursor:col-resize; background:transparent; z-index:15; }
    .ss-col-resize:hover { background:var(--accent); opacity:0.5; }
    .ss-row-header { width:36px; min-width:36px; background:var(--card-raised); border:1px solid var(--border); color:var(--text-muted); font-size:11px; text-align:center; padding:3px 2px; position:sticky; left:0; z-index:5; cursor:default; }
    .ss-cell { border:1px solid var(--border); padding:3px 5px; font-size:13px; color:var(--text); cursor:cell; position:relative; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; background:var(--card); min-height:26px; height:26px; }
    .ss-cell:hover { background:rgba(255,255,255,0.04); }
    .ss-cell.ss-selected { background:rgba(59,130,246,0.18) !important; }
    .ss-cell.ss-active { background:rgba(59,130,246,0.28) !important; }
    .ss-cell.ss-sel-top    { border-top:2px solid #3b82f6 !important; }
    .ss-cell.ss-sel-bottom { border-bottom:2px solid #3b82f6 !important; }
    .ss-cell.ss-sel-left   { border-left:2px solid #3b82f6 !important; }
    .ss-cell.ss-sel-right  { border-right:2px solid #3b82f6 !important; }
    .ss-cell-text { pointer-events:none; display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .ss-fill-handle { position:absolute; right:-3px; bottom:-3px; width:7px; height:7px; background:#3b82f6; border:1.5px solid var(--bg); cursor:crosshair; z-index:20; }
    #ss-context-menu { font-size:13px; }
    .ss-menu-item { padding:7px 18px; cursor:pointer; white-space:nowrap; color:var(--text); }
    .ss-menu-item:hover { background:rgba(255,255,255,0.08); }
    .ss-menu-sep { height:1px; background:var(--border); margin:3px 0; }
    .ss-menu-submenu { position:relative; }
    .ss-submenu { display:none; position:absolute; left:100%; top:0; background:var(--card); border:1px solid var(--border); border-radius:8px; min-width:180px; box-shadow:0 8px 24px rgba(0,0,0,0.4); }
    .ss-menu-submenu:hover > .ss-submenu { display:block; }
    #ss-table { border-collapse:collapse; table-layout:fixed; }
    #ss-table th, #ss-table td { box-sizing:border-box; }

    /* ── Ribbon Toolbar ─────────────────────────────────────────────────── */
    .ss-ribbon { display:flex; align-items:stretch; gap:0; padding:4px 8px; background:var(--card-raised); border-bottom:1px solid var(--border); flex-wrap:wrap; min-height:64px; }
    .ss-ribbon-group { display:flex; flex-direction:column; align-items:center; padding:2px 4px; min-width:0; }
    .ss-ribbon-btns { display:flex; align-items:center; gap:2px; flex:1; }
    .ss-ribbon-label { font-size:10px; color:var(--text-muted); text-align:center; padding-top:2px; white-space:nowrap; border-top:1px solid var(--border); width:100%; margin-top:2px; padding-top:3px; }
    .ss-ribbon-sep { width:1px; background:var(--border); margin:4px 6px; align-self:stretch; }
    .ss-rb { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1px; padding:3px 5px; min-width:36px; height:44px; background:transparent; border:1px solid transparent; border-radius:5px; color:var(--text-muted); font-size:10px; cursor:pointer; white-space:nowrap; transition:all 0.12s; line-height:1.2; }
    .ss-rb svg { width:18px; height:18px; flex-shrink:0; }
    .ss-rb:hover { background:rgba(255,255,255,0.08); border-color:var(--border); color:var(--text); }
    .ss-rb:active { background:rgba(59,130,246,0.2); }
    .ss-rb.ss-rb-active { background:rgba(59,130,246,0.2); border-color:#3b82f6; color:var(--accent); }
    .ss-rb-tall { height:52px; font-size:11px; }
    .ss-rb-tall svg { width:22px; height:22px; }
    .ss-rb-icon { min-width:30px; width:30px; padding:3px; font-size:0; }
    .ss-rb-icon svg { width:20px; height:20px; }
    .ss-rb-col { display:flex; flex-direction:column; gap:1px; }
    .ss-rb-col .ss-rb { height:21px; padding:1px 4px; font-size:10px; }
    .ss-rb-col .ss-rb svg { width:13px; height:13px; }
    .ss-rb-color { min-width:28px; width:28px; height:28px; padding:2px; font-size:0; }
    .ss-rb-color svg { width:22px; height:22px; }
    .ss-rb-danger:hover { color:var(--danger) !important; border-color:var(--danger) !important; }

"""


def render_portal_html() -> str:
    events = get_live_events()
    rows = []
    for e in events:
        ts = str(e.get("server_timestamp", ""))[:19].replace("T", " ")
        actor = e.get("actor", "")
        part = f"{e.get('part_name', '')} <small style='color:#8b9eb3;'>({e.get('tracking_code', '')})</small>"
        action = f"<span style='color:var(--accent);font-weight:700;'>{e.get('action', '')}</span> ({e.get('detail', '')})"
        qty = str(e.get("quantity", ""))
        notes = e.get("notes", "") or "—"
        rows.append(f"<tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'><td style='padding: 10px 14px;'>{ts}</td><td style='padding: 10px 14px;'><b>{actor}</b></td><td style='padding: 10px 14px;'>{part}</td><td style='padding: 10px 14px;'>{action}</td><td style='padding: 10px 14px;'><b>{qty}</b></td><td style='padding: 10px 14px;color:#8b9eb3;'>{notes}</td></tr>")
    table_rows = "".join(rows) if rows else "<tr><td colspan='6' style='text-align:center;color:#8b9eb3;padding:16px;'>Chưa có báo cáo nào được gửi.</td></tr>"

    public_url = get_public_tunnel_url()
    public_mobile_url = f"{public_url}/tracking/mobile" if public_url else "/tracking/mobile"
    public_qr = make_qr_data_uri(public_mobile_url) if public_url else ""

    local_ip = get_local_ip()
    wifi_mobile_url = f"{lan_url_scheme()}://{local_ip}:8000/tracking/mobile"
    wifi_qr = make_qr_data_uri(wifi_mobile_url)

    stats = get_stats()
    total_t = max(stats['tracking'], 1)
    pct_deliv = round(stats['deliv'] * 100 / total_t, 1)
    pct_pack = round(stats['packed'] * 100 / total_t, 1)
    pct_qc = round(stats['qc'] * 100 / total_t, 1)
    pct_prod = round(stats['in_prod'] * 100 / total_t, 1)
    pct_done = round((stats['qc'] + stats['packed'] + stats['deliv']) * 100 / total_t, 1)

    html = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HMS QR Product Manager — Trung Tâm Điều Hành Sản Xuất</title>
  <link rel="manifest" href="/manifest.json">
  <link rel="icon" type="image/png" href="/static/favicon.png">
  <meta name="theme-color" content="#0d1520">
  <style>
    :root {{
      --bg: #0d1520;
      --card-bg: #141f2d;
      --card-raised: #1c2b3d;
      --border: #283e54;
      --accent: #00d2b4;
      --accent-dim: rgba(0, 210, 180, 0.12);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --text: #f0f6fc;
      --text-muted: #8b9eb3;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: var(--font);
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 0;
      line-height: 1.5;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(20, 31, 45, 0.94);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--border);
      padding: 14px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .brand-logo {{
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #00d2b4 0%, #008775 100%);
      border-radius: 9px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 900;
      color: #0d1520;
      font-size: 19px;
    }}
    .brand h1 {{
      font-size: 17px;
      margin: 0;
      font-weight: 800;
      letter-spacing: 0.5px;
      color: var(--text);
    }}
    .brand-sub {{
      font-size: 12px;
      color: var(--text-muted);
    }}
    .header-links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 9px 16px;
      border-radius: 9px;
      font-size: 14px;
      font-weight: 700;
      text-decoration: none;
      transition: all 0.15s ease;
      cursor: pointer;
      border: 1px solid transparent;
    }}
    .btn-primary {{
      background: linear-gradient(135deg, #00d2b4 0%, #00a48c 100%);
      color: #0d1520;
      box-shadow: 0 4px 14px rgba(0, 210, 180, 0.25);
    }}
    .btn-primary:hover {{
      opacity: 0.92;
      transform: translateY(-1px);
    }}
    .btn-outline {{
      background: var(--card-bg);
      color: var(--text);
      border-color: var(--border);
    }}
    .btn-outline:hover {{
      background: var(--card-raised);
      border-color: var(--accent);
      color: var(--accent);
    }}
    .btn-sm {{
      padding: 6px 12px;
      font-size: 13px;
    }}
    .btn-success {{
      background: #10b981;
      color: #fff;
    }}
    .btn:active {{ transform: scale(0.97); }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px 16px 60px;
    }}
    .nav-tabs {{
      display: flex;
      gap: 8px;
      border-bottom: 2px solid var(--border);
      margin-bottom: 24px;
      overflow-x: auto;
      padding-bottom: 2px;
    }}
    .nav-tab {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 15px;
      font-weight: 700;
      padding: 12px 18px;
      cursor: pointer;
      border-bottom: 3px solid transparent;
      margin-bottom: -2px;
      white-space: nowrap;
      transition: all 0.15s;
    }}
    .nav-tab:hover {{
      color: var(--text);
    }}
    .nav-tab.active {{
      color: var(--accent);
      border-bottom-color: var(--accent);
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}
    .stat-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 20px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    }}
    .stat-num {{
      font-size: 28px;
      font-weight: 800;
      color: var(--accent);
      margin-bottom: 2px;
    }}
    .stat-label {{
      font-size: 12px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      font-weight: 700;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      margin-bottom: 24px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .card-title {{
      font-size: 17px;
      font-weight: 800;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
    }}
    .qr-catalog-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
    }}
    .qr-label-card {{
      background: var(--card-raised);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      position: relative;
      transition: border-color 0.2s;
    }}
    .qr-label-card:hover {{
      border-color: var(--accent);
    }}
    .qr-card-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 8px;
    }}
    .qr-card-comp {{
      font-size: 12px;
      font-weight: 800;
      color: var(--accent);
      background: var(--accent-dim);
      padding: 2px 8px;
      border-radius: 4px;
    }}
    .qr-card-qty {{
      font-size: 13px;
      font-weight: 800;
      color: var(--text);
    }}
    .qr-card-title {{
      font-size: 15px;
      font-weight: 700;
      margin-bottom: 10px;
      word-break: break-word;
      color: #fff;
    }}
    .qr-card-body {{
      display: flex;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
    }}
    .qr-card-img {{
      width: 100px;
      height: 100px;
      background: #fff;
      padding: 6px;
      border-radius: 8px;
      flex-shrink: 0;
    }}
    .qr-card-img img {{
      width: 100%;
      height: 100%;
      display: block;
    }}
    .qr-card-meta {{
      font-size: 12px;
      color: var(--text-muted);
      line-height: 1.4;
    }}
    .qr-card-meta b {{
      color: var(--text);
    }}
    .qr-card-actions {{
      display: flex;
      gap: 6px;
      margin-top: auto;
    }}
    .tab-pane {{
      display: none;
    }}
    .tab-pane.active {{
      display: block;
    }}
    .toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--success);
      color: #fff;
      font-weight: 700;
      padding: 12px 20px;
      border-radius: 10px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.4);
      display: none;
      z-index: 1000;
    }}
    /* PRINT STYLES FOR THERMAL & STICKER LABELS */
    @media print {{
      body * {{ visibility: hidden; }}
      #printable-area, #printable-area * {{ visibility: visible; }}
      #printable-area {{
        position: absolute;
        left: 0;
        top: 0;
        width: 100%;
        background: #fff !important;
        color: #000 !important;
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 12px !important;
        padding: 10px !important;
      }}
      .print-label {{
        border: 2px solid #000 !important;
        padding: 10px !important;
        page-break-inside: avoid !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 12px !important;
        border-radius: 6px !important;
      }}
      .print-label img {{
        width: 90px !important;
        height: 90px !important;
      }}
      .print-label-info {{
        font-size: 11pt !important;
        line-height: 1.3 !important;
      }}
    }}

{_SS_CSS}  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-logo">⚡</div>
      <div>
        <h1>HỆ THỐNG ĐIỀU HÀNH SẢN XUẤT & QR</h1>
        <div class="brand-sub">HMS Industrial Management · Real-time Control Center</div>
      </div>
    </div>
    <div class="header-links">
      <a href="#" onclick="downloadExcelReport(event)" class="btn btn-outline" id="excel-export-btn" style="background:#064e3b;border-color:#059669;color:#6ee7b7;">📥 Xuất Báo Cáo Excel</a>
      <a href="{public_mobile_url}" target="_blank" class="btn btn-primary">📱 Mở Mobile Scanner</a>
      <a href="/docs" target="_blank" class="btn btn-outline">📑 API Swagger</a>
      <a href="/health/readiness/database" target="_blank" class="btn btn-outline">🩺 DB Health</a>
    </div>
  </header>

  <main class="container">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-num">{stats['products']}</div>
        <div class="stat-label">Sản Phẩm Master</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{stats['pos']}</div>
        <div class="stat-label">Đơn Hàng / PO</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{stats['tracking']}</div>
        <div class="stat-label">Mã QR Tracking</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{stats['operators']}</div>
        <div class="stat-label">Nhân Sự Xưởng</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{stats['machining']}</div>
        <div class="stat-label">Công Đoạn Chuẩn</div>
      </div>
    </div>

    <!-- MAIN NAV TABS -->
    <div class="nav-tabs">
      <button class="nav-tab active" onclick="switchTab('tab-live')">📊 TIẾN ĐỘ & ĐIỀU ĐỘ THỰC TẾ</button>
      <button class="nav-tab" onclick="switchTab('tab-qr')">🏷️ STUDIO IN NHÃN QR ({stats['tracking']})</button>
      <button class="nav-tab" onclick="switchTab('tab-excel')">📋 DÁN & ĐỒNG BỘ EXCEL</button>
      <button class="nav-tab" onclick="switchTab('tab-connect')">📶 KẾT NỐI CAMERA DI ĐỘNG</button>
    </div>

    <!-- TAB 1: LIVE FEED & MONITORING -->
    <div id="tab-live" class="tab-pane active">
      <!-- VISUAL PRODUCTION PROGRESS BAR -->
      <div class="card" style="margin-bottom: 20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <div style="font-weight:800; font-size:15px; color:var(--text); display:flex; align-items:center; gap:8px;">
            <span>📈</span> PHÂN BỔ TIẾN ĐỘ SẢN XUẤT ({stats['tracking']} ĐƠN HÀNG)
          </div>
          <div style="font-size:13px; color:var(--text-muted);">
            Tỷ lệ QC & Hoàn thành: <b style="color:var(--success);">{pct_done}%</b>
          </div>
        </div>
        <div style="height: 12px; width:100%; background: var(--card-raised); border-radius: 6px; overflow:hidden; display:flex; margin-bottom:12px;">
          <div style="width:{pct_deliv}%; background:#8b5cf6;" title="Đã giao hàng: {stats['deliv']}"></div>
          <div style="width:{pct_pack}%; background:#3b82f6;" title="Đã đóng gói: {stats['packed']}"></div>
          <div style="width:{pct_qc}%; background:#10b981;" title="QC đạt: {stats['qc']}"></div>
          <div style="width:{pct_prod}%; background:#00d2b4;" title="Đang gia công: {stats['in_prod']}"></div>
        </div>
        <div style="display:flex; gap:16px; flex-wrap:wrap; font-size:12px; font-weight:700;">
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="width:10px; height:10px; background:#00d2b4; border-radius:2px;"></span>
            <span>Đang gia công: <b style="color:#00d2b4;">{stats['in_prod']}</b> ({pct_prod}%)</span>
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="width:10px; height:10px; background:#10b981; border-radius:2px;"></span>
            <span>QC đạt: <b style="color:#10b981;">{stats['qc']}</b> ({pct_qc}%)</span>
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="width:10px; height:10px; background:#3b82f6; border-radius:2px;"></span>
            <span>Đã đóng gói: <b style="color:#3b82f6;">{stats['packed']}</b> ({pct_pack}%)</span>
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="width:10px; height:10px; background:#8b5cf6; border-radius:2px;"></span>
            <span>Đã xuất xưởng: <b style="color:#8b5cf6;">{stats['deliv']}</b> ({pct_deliv}%)</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h2 class="card-title"><span>📡</span> NHẬT KÝ TIẾN ĐỘ SẢN XUẤT THỜI GIAN THỰC (LIVE ACTIVITY FEED)</h2>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <span style="font-size:13px;color:var(--success);display:flex;align-items:center;gap:6px;">
              <span style="width:8px;height:8px;background:var(--success);border-radius:50%;display:inline-block;box-shadow:0 0 8px var(--success);"></span>
              Tự động cập nhật mỗi 3s
            </span>
            <button onclick="copyFeedToExcel()" class="btn btn-outline btn-sm" style="color:var(--accent);border-color:var(--accent);">📋 Copy Bảng Sang Excel (TSV)</button>
            <button onclick="autoRefreshFeed()" class="btn btn-outline btn-sm">🔄 Làm Mới</button>
          </div>
        </div>
        <div style="overflow-x: auto; border: 1px solid var(--border); border-radius: 10px;">
          <table style="width: 100%; border-collapse: collapse; font-size: 14px; text-align: left;">
            <thead>
              <tr style="background: var(--card-raised); border-bottom: 1px solid var(--border); color: var(--text-muted);">
                <th style="padding: 12px 14px;">Thời gian</th>
                <th style="padding: 12px 14px;">Nhân sự thực hiện</th>
                <th style="padding: 12px 14px;">Chi tiết / Mã theo dõi</th>
                <th style="padding: 12px 14px;">Công đoạn / Thao tác</th>
                <th style="padding: 12px 14px;">Số lượng</th>
                <th style="padding: 12px 14px;">Ghi chú</th>
              </tr>
            </thead>
            <tbody id="feed-tbody">
              {table_rows}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 2: QR LABEL PRINTING STUDIO -->
    <div id="tab-qr" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div>
            <h2 class="card-title"><span>🏷️</span> STUDIO QUẢN LÝ & IN NHÃN QR TRUY VẾT HÀNG LOẠT</h2>
            <div style="font-size:13px;color:var(--text-muted);margin-top:4px;">
              Hỗ trợ tìm kiếm, lọc theo khách hàng và in tem nhãn nhiệt / A4 cho toàn bộ chi tiết trong xưởng.
            </div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <input id="qr-search-input" oninput="filterQrCatalog()" placeholder="🔍 Tìm theo mã SP, tên chi tiết, mã tracking..." style="min-width: 260px; padding: 8px 12px;">
            <select id="qr-comp-filter" onchange="filterQrCatalog()" style="padding: 8px 12px;">
              <option value="">Tất cả khách hàng</option>
            </select>
            <button onclick="copyCatalogToExcel()" class="btn btn-outline btn-sm" style="color:var(--accent);border-color:var(--accent);">📋 Copy Danh Sách Sang Excel</button>
            <button onclick="printLabels()" class="btn btn-primary btn-sm">🖨️ IN CÁC NHÃN ĐANG CHỌN</button>
          </div>
        </div>

        <div id="qr-catalog-container" class="qr-catalog-grid">
          <div style="text-align:center;padding:30px;color:var(--text-muted);grid-column:1/-1;">Đang tải danh sách nhãn QR...</div>
        </div>
      </div>
    </div>

    <!-- TAB 3: SPREADSHEET EDITOR + EXCEL IMPORT -->
    <div id="tab-excel" class="tab-pane">

      <!-- SPREADSHEET EDITOR CARD -->
      <div class="card" style="border-color:var(--accent);background:linear-gradient(135deg,rgba(0,210,180,0.05) 0%,rgba(20,31,45,1) 100%);margin-bottom:20px;padding:0;">

        <!-- TITLE ROW -->
        <div style="padding:12px 16px 8px;border-bottom:1px solid var(--border);">
          <h2 class="card-title" style="color:var(--accent);margin:0;font-size:14px;"><span>🗒️</span> BẢNG TÍNH TRỰC TIẾP — NHẬP LIỆU VÀ CÔNG THỨC NHƯ EXCEL</h2>
        </div>

        <!-- RIBBON TOOLBAR -->
        <div class="ss-ribbon">

          <!-- GROUP: Clipboard -->
          <div class="ss-ribbon-group">
            <div class="ss-ribbon-btns">
              <button class="ss-rb ss-rb-tall" onclick="ssPasteFromClipboard()" title="Dán (Ctrl+V)">
                <svg viewBox="0 0 20 20"><rect x="5" y="3" width="10" height="2" rx="1"/><rect x="3" y="4" width="14" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="5" y="8" width="10" height="1.5" rx="0.75"/><rect x="5" y="11" width="7" height="1.5" rx="0.75"/></svg>
                <span>Dán</span>
              </button>
              <div class="ss-rb-col">
                <button class="ss-rb" onclick="ssCopyToClipboard()" title="Sao chép (Ctrl+C)">
                  <svg viewBox="0 0 20 20"><rect x="7" y="2" width="9" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="4" y="6" width="9" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                  Copy
                </button>
                <button class="ss-rb" onclick="ssCutToClipboard()" title="Cắt (Ctrl+X)">
                  <svg viewBox="0 0 20 20"><path d="M5 5 l10 10 M15 5 l-10 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="6" cy="15" r="2" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="14" cy="15" r="2" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                  Cắt
                </button>
              </div>
            </div>
            <div class="ss-ribbon-label">Clipboard</div>
          </div>

          <div class="ss-ribbon-sep"></div>

          <!-- GROUP: Font -->
          <div class="ss-ribbon-group">
            <div class="ss-ribbon-btns">
              <button class="ss-rb ss-rb-icon" onclick="ssToggleBold()" title="Đậm (Ctrl+B)" id="ss-btn-bold">
                <svg viewBox="0 0 20 20"><text x="4" y="16" font-size="14" font-weight="900" font-family="serif" fill="currentColor">B</text></svg>
              </button>
              <button class="ss-rb ss-rb-icon" onclick="ssToggleItalic()" title="Nghiêng (Ctrl+I)" id="ss-btn-italic">
                <svg viewBox="0 0 20 20"><text x="5" y="16" font-size="14" font-style="italic" font-family="serif" fill="currentColor">I</text></svg>
              </button>
              <button class="ss-rb ss-rb-icon" onclick="ssToggleUnderline()" title="Gạch chân (Ctrl+U)" id="ss-btn-underline">
                <svg viewBox="0 0 20 20"><text x="5" y="14" font-size="13" text-decoration="underline" font-family="sans-serif" fill="currentColor">U</text><line x1="3" y1="17" x2="17" y2="17" stroke="currentColor" stroke-width="1.5"/></svg>
              </button>
              <div class="ss-rb-col">
                <button class="ss-rb ss-rb-color" title="Màu chữ" onclick="document.getElementById('ss-pick-fg').click()">
                  <svg viewBox="0 0 20 20"><text x="3" y="14" font-size="12" font-weight="700" fill="currentColor">A</text><rect x="3" y="15" width="10" height="2.5" id="ss-fgbar" fill="#e74c3c"/></svg>
                  <input type="color" id="ss-pick-fg" value="#e74c3c" style="display:none" oninput="document.getElementById('ss-fgbar').setAttribute('fill',this.value);ssSetColor(this.value)">
                </button>
                <button class="ss-rb ss-rb-color" title="Màu nền ô" onclick="document.getElementById('ss-pick-bg').click()">
                  <svg viewBox="0 0 20 20"><path d="M4 14 L10 4 L16 14 Z" fill="currentColor" opacity="0.7"/><rect x="3" y="15" width="14" height="2.5" id="ss-bgbar" fill="#f39c12"/></svg>
                  <input type="color" id="ss-pick-bg" value="#f39c12" style="display:none" oninput="document.getElementById('ss-bgbar').setAttribute('fill',this.value);ssSetBg(this.value)">
                </button>
              </div>
              <button class="ss-rb ss-rb-icon" onclick="ssClearFormat()" title="Xóa định dạng">
                <svg viewBox="0 0 20 20"><path d="M4 5h12M8 5v10M4 15h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/><line x1="13" y1="10" x2="18" y2="15" stroke="var(--danger)" stroke-width="1.5" stroke-linecap="round"/><line x1="18" y1="10" x2="13" y2="15" stroke="var(--danger)" stroke-width="1.5" stroke-linecap="round"/></svg>
              </button>
            </div>
            <div class="ss-ribbon-label">Font</div>
          </div>

          <div class="ss-ribbon-sep"></div>

          <!-- GROUP: Alignment -->
          <div class="ss-ribbon-group">
            <div class="ss-ribbon-btns">
              <button class="ss-rb ss-rb-icon" onclick="ssSetAlign('left')" title="Căn trái">
                <svg viewBox="0 0 20 20"><line x1="3" y1="6" x2="17" y2="6" stroke="currentColor" stroke-width="1.5"/><line x1="3" y1="10" x2="13" y2="10" stroke="currentColor" stroke-width="1.5"/><line x1="3" y1="14" x2="17" y2="14" stroke="currentColor" stroke-width="1.5"/></svg>
              </button>
              <button class="ss-rb ss-rb-icon" onclick="ssSetAlign('center')" title="Căn giữa">
                <svg viewBox="0 0 20 20"><line x1="3" y1="6" x2="17" y2="6" stroke="currentColor" stroke-width="1.5"/><line x1="6" y1="10" x2="14" y2="10" stroke="currentColor" stroke-width="1.5"/><line x1="3" y1="14" x2="17" y2="14" stroke="currentColor" stroke-width="1.5"/></svg>
              </button>
              <button class="ss-rb ss-rb-icon" onclick="ssSetAlign('right')" title="Căn phải">
                <svg viewBox="0 0 20 20"><line x1="3" y1="6" x2="17" y2="6" stroke="currentColor" stroke-width="1.5"/><line x1="7" y1="10" x2="17" y2="10" stroke="currentColor" stroke-width="1.5"/><line x1="3" y1="14" x2="17" y2="14" stroke="currentColor" stroke-width="1.5"/></svg>
              </button>
              <button class="ss-rb ss-rb-icon" onclick="ssToggleWrap()" title="Xuống dòng">
                <svg viewBox="0 0 20 20"><line x1="3" y1="7" x2="17" y2="7" stroke="currentColor" stroke-width="1.5"/><path d="M17 11 H9 M9 11 L12 8 M9 11 L12 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/><line x1="3" y1="15" x2="11" y2="15" stroke="currentColor" stroke-width="1.5"/></svg>
              </button>
            </div>
            <div class="ss-ribbon-label">Căn lề</div>
          </div>

          <div class="ss-ribbon-sep"></div>

          <!-- GROUP: Number Format -->
          <div class="ss-ribbon-group">
            <div class="ss-ribbon-btns">
              <button class="ss-rb" onclick="ssSetFmt('general')" title="Chung">
                <svg viewBox="0 0 20 20"><text x="3" y="15" font-size="11" fill="currentColor" font-family="monospace">ABC</text></svg>
                Chung
              </button>
              <button class="ss-rb" onclick="ssSetFmt('integer')" title="Số nguyên">
                <svg viewBox="0 0 20 20"><text x="2" y="15" font-size="11" fill="currentColor" font-family="monospace">123</text></svg>
                Số
              </button>
              <button class="ss-rb" onclick="ssSetFmt('currency')" title="Tiền tệ VND">
                <svg viewBox="0 0 20 20"><text x="5" y="15" font-size="13" fill="currentColor" font-family="sans-serif">₫</text></svg>
                Tiền
              </button>
              <button class="ss-rb" onclick="ssSetFmt('percent')" title="Phần trăm">
                <svg viewBox="0 0 20 20"><text x="3" y="15" font-size="13" fill="currentColor">%</text></svg>
                %
              </button>
              <button class="ss-rb" onclick="ssSetFmt('date')" title="Ngày tháng">
                <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="3" y1="8" x2="17" y2="8" stroke="currentColor" stroke-width="1.5"/><line x1="7" y1="4" x2="7" y2="7" stroke="currentColor" stroke-width="1.5"/><line x1="13" y1="4" x2="13" y2="7" stroke="currentColor" stroke-width="1.5"/><text x="5" y="15" font-size="8" fill="currentColor">15</text></svg>
                Ngày
              </button>
              <button class="ss-rb" onclick="ssSetFmt('number')" title="Số thập phân">
                <svg viewBox="0 0 20 20"><text x="1" y="15" font-size="10" fill="currentColor" font-family="monospace">1.23</text></svg>
                0.00
              </button>
            </div>
            <div class="ss-ribbon-label">Định dạng số</div>
          </div>

          <div class="ss-ribbon-sep"></div>

          <!-- GROUP: Cells -->
          <div class="ss-ribbon-group">
            <div class="ss-ribbon-btns">
              <div class="ss-rb-col">
                <button class="ss-rb" onclick="ssInsertRowAbove()" title="Chèn hàng phía trên">
                  <svg viewBox="0 0 20 20"><rect x="3" y="10" width="14" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="3" x2="10" y2="9" stroke="var(--success)" stroke-width="2" stroke-linecap="round"/><line x1="7" y1="6" x2="13" y2="6" stroke="var(--success)" stroke-width="2" stroke-linecap="round"/></svg>
                  Chèn hàng
                </button>
                <button class="ss-rb" onclick="ssDeleteRows()" title="Xóa hàng">
                  <svg viewBox="0 0 20 20"><rect x="3" y="10" width="14" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="7" y1="5" x2="13" y2="5" stroke="var(--danger)" stroke-width="2" stroke-linecap="round"/><line x1="7" y1="3" x2="7" y2="7" stroke="var(--danger)" stroke-width="1.5" stroke-linecap="round"/><line x1="13" y1="3" x2="13" y2="7" stroke="var(--danger)" stroke-width="1.5" stroke-linecap="round"/></svg>
                  Xóa hàng
                </button>
              </div>
              <div class="ss-rb-col">
                <button class="ss-rb" onclick="ssInsertColLeft()" title="Chèn cột bên trái">
                  <svg viewBox="0 0 20 20"><rect x="10" y="3" width="7" height="14" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="3" y1="10" x2="9" y2="10" stroke="var(--success)" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="7" x2="6" y2="13" stroke="var(--success)" stroke-width="2" stroke-linecap="round"/></svg>
                  Chèn cột
                </button>
                <button class="ss-rb" onclick="ssDeleteCols()" title="Xóa cột">
                  <svg viewBox="0 0 20 20"><rect x="10" y="3" width="7" height="14" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="4" y1="7" x2="8" y2="11" stroke="var(--danger)" stroke-width="2" stroke-linecap="round"/><line x1="8" y1="7" x2="4" y2="11" stroke="var(--danger)" stroke-width="2" stroke-linecap="round"/></svg>
                  Xóa cột
                </button>
              </div>
              <button class="ss-rb" onclick="ssAddRow()" title="Thêm hàng cuối">
                <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="9" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="14" x2="10" y2="19" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/><line x1="7" y1="16.5" x2="13" y2="16.5" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/></svg>
                Thêm hàng
              </button>
            </div>
            <div class="ss-ribbon-label">Ô / Hàng / Cột</div>
          </div>

          <div class="ss-ribbon-sep"></div>

          <!-- GROUP: Edit -->
          <div class="ss-ribbon-group">
            <div class="ss-ribbon-btns">
              <div class="ss-rb-col">
                <button class="ss-rb" onclick="ssFillDown()" title="Fill xuống (Ctrl+D)">
                  <svg viewBox="0 0 20 20"><rect x="5" y="3" width="10" height="5" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="9" x2="10" y2="17" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/><path d="M7 14 L10 17 L13 14" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                  Fill ↓
                </button>
                <button class="ss-rb" onclick="ssFillRight()" title="Fill phải (Ctrl+R)">
                  <svg viewBox="0 0 20 20"><rect x="3" y="5" width="5" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="9" y1="10" x2="17" y2="10" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/><path d="M14 7 L17 10 L14 13" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                  Fill →
                </button>
              </div>
              <div class="ss-rb-col">
                <button class="ss-rb" onclick="ssUndo()" title="Hoàn tác (Ctrl+Z)">
                  <svg viewBox="0 0 20 20"><path d="M4 10 A6 6 0 1 1 10 16" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/><path d="M4 6 L4 10 L8 10" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  Hoàn tác
                </button>
                <button class="ss-rb" onclick="ssRedo()" title="Làm lại (Ctrl+Y)">
                  <svg viewBox="0 0 20 20"><path d="M16 10 A6 6 0 1 0 10 16" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/><path d="M16 6 L16 10 L12 10" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  Làm lại
                </button>
              </div>
              <button class="ss-rb" onclick="ssDeleteSelection()" title="Xóa nội dung (Delete)">
                <svg viewBox="0 0 20 20"><path d="M5 5 L15 15 M15 5 L5 15" stroke="var(--danger)" stroke-width="2" stroke-linecap="round"/></svg>
                Xóa ô
              </button>
            </div>
            <div class="ss-ribbon-label">Chỉnh sửa</div>
          </div>

          <div class="ss-ribbon-sep"></div>

          <!-- GROUP: Data -->
          <div class="ss-ribbon-group">
            <div class="ss-ribbon-btns">
              <button class="ss-rb ss-rb-tall" onclick="ssImportFromClipboard()" title="Dán toàn bộ từ Excel vào bảng">
                <svg viewBox="0 0 20 20"><rect x="3" y="3" width="14" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="14" x2="10" y2="18" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/><path d="M7 15 L10 18 L13 15" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/><line x1="6" y1="7" x2="14" y2="7" stroke="currentColor" stroke-width="1.2"/><line x1="6" y1="10" x2="11" y2="10" stroke="currentColor" stroke-width="1.2"/></svg>
                <span>Tải từ<br>Excel</span>
              </button>
              <div class="ss-rb-col">
                <button class="ss-rb" onclick="ssExportToClipboard()" title="Copy toàn bộ bảng → dán vào Excel" style="color:var(--accent);">
                  <svg viewBox="0 0 20 20"><rect x="3" y="7" width="14" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="3" x2="10" y2="7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M7 5 L10 2 L13 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
                  Copy → Excel
                </button>
                <button class="ss-rb" onclick="ssFillSample()" title="Điền dữ liệu mẫu">
                  <svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="6" x2="10" y2="14" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="10" x2="14" y2="10" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/></svg>
                  Dữ liệu mẫu
                </button>
              </div>
              <button class="ss-rb ss-rb-danger" onclick="ssClear()" title="Xóa toàn bộ bảng">
                <svg viewBox="0 0 20 20"><path d="M6 4 h8 l1 2 H5 Z" fill="currentColor" opacity="0.7"/><rect x="4" y="6" width="12" height="11" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="8" y1="9" x2="8" y2="14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><line x1="12" y1="9" x2="12" y2="14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
                Xóa bảng
              </button>
            </div>
            <div class="ss-ribbon-label">Dữ liệu</div>
          </div>

        </div><!-- end ribbon -->

        <!-- FORMULA BAR -->
        <div style="display:flex;align-items:center;gap:8px;margin:0;background:var(--card-raised);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:5px 10px;">
          <div id="ss-cell-addr" style="font-family:monospace;font-size:13px;color:var(--accent);min-width:50px;font-weight:700;text-align:center;background:var(--card);border:1px solid var(--border);border-radius:4px;padding:2px 6px;">A1</div>
          <div style="color:var(--border);font-size:18px;line-height:1;">│</div>
          <span style="font-size:13px;color:var(--accent);font-style:italic;font-weight:700;margin-right:2px;">fx</span>
          <input id="ss-formula-bar" type="text" placeholder="Nhập giá trị hoặc công thức: =SUM(C2:C10)"
            style="flex:1;background:transparent;border:none;outline:none;color:var(--text);font-family:monospace;font-size:13px;"
            oninput="ssFormulaBarInput()" onkeydown="ssFormulaBarKeyDown(event)">
        </div>
        <!-- GRID -->
        <div id="ss-container" style="overflow:auto;border:1px solid var(--border);border-radius:10px;max-height:420px;">
          <table id="ss-table" style="border-collapse:collapse;font-size:13px;table-layout:fixed;min-width:900px;">
            <thead id="ss-thead"></thead>
            <tbody id="ss-tbody"></tbody>
          </table>
        </div>
        <!-- STATUS BAR -->
        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:8px;flex-wrap:wrap;gap:8px;">
          <div id="ss-status" style="font-size:12px;color:var(--text-muted);">Nhấp ô để chỉnh sửa • Tab/Enter di chuyển • Ctrl+Z hoàn tác • Delete xóa ô</div>
          <div id="ss-aggregate" style="font-size:12px;color:var(--accent);font-family:monospace;display:flex;gap:14px;"></div>
        </div>
        <!-- IMPORT ACTIONS -->
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:14px;padding-top:14px;border-top:1px solid var(--border);">
          <button onclick="ssPreviewImport()" class="btn btn-primary" style="padding:10px 20px;">🔍 Phân Tích &amp; Xem Trước</button>
          <button onclick="ssDoImport()" class="btn btn-success" style="padding:10px 22px;">📥 Nạp Dữ Liệu &amp; Cấp Mã QR</button>
          <button onclick="ssCopyPreview()" class="btn btn-outline btn-sm">📋 Copy Bảng Preview → Excel</button>
        </div>
        <div id="ss-import-status" style="font-size:14px;margin-top:12px;display:none;"></div>
        <div id="ss-preview-wrap" style="display:none;max-height:340px;overflow-y:auto;border:1px solid var(--border);border-radius:10px;margin-top:10px;">
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
              <tr style="background:var(--card-raised);color:var(--text-muted);">
                <th style="padding:9px 11px;">Dòng</th><th style="padding:9px 11px;">Khách hàng</th>
                <th style="padding:9px 11px;">Tên chi tiết</th><th style="padding:9px 11px;">Số lượng</th>
                <th style="padding:9px 11px;">ĐVT</th><th style="padding:9px 11px;">Vật liệu</th>
                <th style="padding:9px 11px;">Bề mặt</th><th style="padding:9px 11px;">Kích thước</th>
                <th style="padding:9px 11px;">Đơn giá</th>
              </tr>
            </thead>
            <tbody id="ss-preview-tbody"></tbody>
          </table>
        </div>
      </div>

      <!-- FILE SYNC CARD -->
      <div class="card">
        <div class="card-header">
          <div>
            <h2 class="card-title"><span>📂</span> ĐỒNG BỘ FILE TỪ THƯ MỤC D:\\DU-LIEU</h2>
            <div style="font-size:13px;color:var(--text-muted);margin-top:4px;">Quét trực tiếp các file Excel tháng hoặc file Báo giá trong ổ đĩa D:\\DU-LIEU.</div>
          </div>
        </div>
        <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:16px;background:var(--card-raised);padding:14px;border-radius:10px;border:1px solid var(--border);">
          <div style="flex:1;min-width:240px;">
            <label style="display:block;font-size:12px;color:var(--text-muted);margin-bottom:4px;font-weight:700;">CHỌN FILE EXCEL TỪ D:\\DU-LIEU:</label>
            <select id="excel-file-select" onchange="onFileSelectChange()" style="width:100%;"></select>
          </div>
          <div style="min-width:180px;">
            <label style="display:block;font-size:12px;color:var(--text-muted);margin-bottom:4px;font-weight:700;">CHỌN SHEET:</label>
            <select id="excel-sheet-select" style="width:100%;"></select>
          </div>
          <div style="align-self:flex-end;display:flex;gap:8px;">
            <button onclick="loadExcelPreview()" class="btn btn-primary btn-sm" style="padding:10px 16px;">🔍 Xem Trước</button>
            <button onclick="doExcelImport()" class="btn btn-success btn-sm" style="padding:10px 16px;">📥 Nạp &amp; Cấp Mã QR</button>
          </div>
        </div>
        <div id="excel-status" style="font-size:14px;margin-bottom:12px;display:none;"></div>
        <div id="excel-preview-wrap" style="display:none;max-height:420px;overflow-y:auto;border:1px solid var(--border);border-radius:10px;">
          <table style="width:100%;border-collapse:collapse;font-size:13px;text-align:left;">
            <thead>
              <tr style="background:var(--card-raised);border-bottom:1px solid var(--border);color:var(--text-muted);">
                <th style="padding:10px 12px;">Dòng</th><th style="padding:10px 12px;">Khách hàng</th>
                <th style="padding:10px 12px;">Tên chi tiết</th><th style="padding:10px 12px;">Số lượng</th>
                <th style="padding:10px 12px;">Đơn vị</th><th style="padding:10px 12px;">Vật liệu</th>
                <th style="padding:10px 12px;">Bề mặt</th><th style="padding:10px 12px;">Kích thước</th>
                <th style="padding:10px 12px;">Đơn giá</th>
              </tr>
            </thead>
            <tbody id="excel-preview-tbody"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 4: CONNECTION & SCANNER SHORTCUTS -->
    <div id="tab-connect" class="tab-pane">
      <div class="card">
        <div class="card-header" style="display:flex; justify-content:space-between; align-items:center;">
          <h2 class="card-title"><span>📶</span> KẾT NỐI CAMERA DI ĐỘNG & QUÉT MÃ TRỰC TIẾP</h2>
          <button type="button" class="btn btn-outline btn-sm" onclick="refreshTunnelStatus()">🔄 Làm Mới Tunnel</button>
        </div>

        <div id="tunnel-status-bar" style="display:none; margin-bottom:14px; padding:10px 14px; border-radius:8px; font-size:13px;"></div>

        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px;">
          <!-- CLOUDFLARE HTTPS -->
          <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(20, 31, 45, 0.6) 100%); border: 1px solid #059669; border-radius: 14px; padding: 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
              <h3 style="margin:0; font-size:16px; color:#34d399;">🌐 Cloudflare Public HTTPS</h3>
              <span style="background:#059669; color:#fff; font-size:11px; font-weight:800; padding:2px 8px; border-radius:4px;">TOÀN CẦU + CAMERA</span>
            </div>
            <div style="display:flex; gap:16px; align-items:center; margin-bottom:14px;">
              {'<div style="background:#fff; padding:8px; border-radius:10px; flex-shrink:0;"><img src="' + public_qr + '" alt="Public HTTPS QR" style="width:120px; height:120px; display:block;"></div>' if public_qr else '<div style="width:136px; height:136px; border-radius:10px; background:rgba(0,0,0,0.3); border:2px dashed #059669; display:flex; align-items:center; justify-content:center; flex-shrink:0; font-size:11px; color:#34d399; text-align:center; padding:8px;">Chưa có<br>tunnel<br>Cloudflare</div>'}
              <div>
                <p style="font-size:13px; color:var(--text-muted); margin:0 0 8px;">Quét bằng camera iPhone/Android bất kỳ. Hoạt động trên mọi mạng 4G/5G/Wi-Fi từ xa và <b>mở khóa quyền camera quét mã</b>.</p>
                <div id="public-url-display" style="font-family:monospace; font-size:13px; color:#34d399; word-break:break-all; background:rgba(0,0,0,0.3); padding:6px 10px; border-radius:6px; margin-bottom:8px;">
                  {public_mobile_url if public_url else '⚠️ Chưa có tunnel — Chạy CHAY_WEB.bat để kích hoạt Cloudflare'}
                </div>
              </div>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
              {'<a href="' + public_mobile_url + '" target="_blank" class="btn btn-primary btn-sm">🚀 Mở Web Mobile</a>' if public_url else ''}
              <button type="button" class="btn btn-outline btn-sm" onclick="copyText('{public_mobile_url if public_url else wifi_mobile_url}')">📋 Sao Chép Link</button>
              <button type="button" class="btn btn-outline btn-sm" onclick="refreshTunnelStatus()">🔄 Cập Nhật</button>
            </div>
          </div>

          <!-- LOCAL WIFI -->
          <div style="background: var(--card-raised); border: 1px solid var(--border); border-radius: 14px; padding: 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
              <h3 style="margin:0; font-size:16px; color:var(--accent);">📶 Mạng Wi-Fi Nội Bộ</h3>
              <span style="background:var(--card-bg); color:var(--accent); font-size:11px; font-weight:800; padding:2px 8px; border-radius:4px; border:1px solid var(--border);">LAN 192.168.x</span>
            </div>
            <div style="display:flex; gap:16px; align-items:center; margin-bottom:14px;">
              <div style="background:#fff; padding:8px; border-radius:10px; flex-shrink:0;">
                <img src="{wifi_qr}" alt="Wi-Fi QR" style="width:120px; height:120px; display:block;">
              </div>
              <div>
                <p style="font-size:13px; color:var(--text-muted); margin:0 0 8px;">Dành cho các thiết bị cùng kết nối mạng Wi-Fi tại xưởng.</p>
                <div style="font-family:monospace; font-size:13px; color:var(--accent); word-break:break-all; background:rgba(0,0,0,0.3); padding:6px 10px; border-radius:6px; margin-bottom:8px;">
                  {wifi_mobile_url}
                </div>
              </div>
            </div>
            <div style="display:flex; gap:8px;">
              <a href="{wifi_mobile_url}" target="_blank" class="btn btn-outline btn-sm">🚀 Mở Link LAN</a>
              <button type="button" class="btn btn-outline btn-sm" onclick="copyText('{wifi_mobile_url}')">📋 Sao Chép Link</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>

  <!-- PRINTABLE HIDDEN CONTAINER -->
  <div id="printable-area"></div>
  <div id="toast" class="toast">Đã sao chép vào bộ nhớ tạm!</div>

  <script>
    let allCatalogItems = [];
    let excelFilesData = [];

    function switchTab(tabId) {{
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      event.currentTarget.classList.add('active');
      const target = document.getElementById(tabId);
      if (target) target.classList.add('active');
      if (tabId === 'tab-qr' && allCatalogItems.length === 0) {{
        loadQrCatalog();
      }}
    }}

    function copyText(text) {{
      navigator.clipboard.writeText(text).then(() =\u003e {{
        const t = document.getElementById('toast');
        t.style.display = 'block';
        setTimeout(() =\u003e {{ t.style.display = 'none'; }}, 2200);
      }});
    }}

    async function downloadExcelReport(e) {{
      e.preventDefault();
      const btn = document.getElementById('excel-export-btn');
      const orig = btn.innerHTML;
      btn.innerHTML = '⏳ Đang tạo báo cáo...';
      btn.style.opacity = '0.6';
      btn.style.pointerEvents = 'none';
      try {{
        const res = await fetch('/api/v1/export/excel');
        if (!res.ok) throw new Error('Lỗi server');
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const cd = res.headers.get('Content-Disposition') || '';
        const fnMatch = cd.match(/filename=([^\\\\s;]+)/);
        a.href = url;
        a.download = fnMatch ? fnMatch[1] : 'HMS_BAO_CAO_SAN_XUAT.xlsx';
        a.click();
        URL.revokeObjectURL(url);
        btn.innerHTML = '✅ Đã tải xong!';
        setTimeout(() =\u003e {{ btn.innerHTML = orig; btn.style.opacity = ''; btn.style.pointerEvents = ''; }}, 2500);
      }} catch(err) {{
        btn.innerHTML = '❌ Lỗi tải xuống';
        setTimeout(() =\u003e {{ btn.innerHTML = orig; btn.style.opacity = ''; btn.style.pointerEvents = ''; }}, 2500);
      }}
    }}

    async function autoRefreshFeed() {{
      try {{
        const res = await fetch('/api/v1/live-feed');
        if (!res.ok) return;
        const data = await res.json();
        if (!data.events) return;
        const rows = data.events.map(e => `
          <tr style='border-bottom: 1px solid rgba(255,255,255,0.05);'>
            <td style='padding: 10px 14px;'>${{(e.server_timestamp || '').slice(0,19).replace('T', ' ')}}</td>
            <td style='padding: 10px 14px;'><b>${{e.actor || ''}}</b></td>
            <td style='padding: 10px 14px;'>${{e.part_name || ''}} <small style='color:var(--text-muted);'>(${{e.tracking_code || ''}})</small></td>
            <td style='padding: 10px 14px;'><span style='color:var(--accent);font-weight:700;'>${{e.action || ''}}</span> (${{e.detail || ''}})</td>
            <td style='padding: 10px 14px;'><b>${{e.quantity ?? ''}}</b></td>
            <td style='padding: 10px 14px;color:var(--text-muted);'>${{e.notes || '—'}}</td>
          </tr>
        `).join('');
        const tbody = document.getElementById('feed-tbody');
        if (tbody && rows) tbody.innerHTML = rows;
      }} catch(e) {{}}
    }}

    async function refreshTunnelStatus() {{
      const bar = document.getElementById('tunnel-status-bar');
      if (!bar) return;
      bar.style.display = 'block';
      bar.style.background = 'rgba(0,210,180,0.08)';
      bar.style.border = '1px solid var(--border)';
      bar.style.color = 'var(--text-muted)';
      bar.textContent = '🔄 Đang kiểm tra trạng thái Cloudflare tunnel...';
      try {{
        const res = await fetch('/api/v1/tunnel-status');
        if (!res.ok) throw new Error('no endpoint');
        const data = await res.json();
        if (data.tunnel_url) {{
          bar.style.background = 'rgba(16,185,129,0.1)';
          bar.style.border = '1px solid #059669';
          bar.style.color = '#34d399';
          bar.innerHTML = `✅ <b>Tunnel đang hoạt động:</b> <a href="${{data.mobile_url}}" target="_blank" style="color:#34d399;">${{data.mobile_url}}</a> — Hãy tải lại trang (F5) để cập nhật QR.`;
        }} else {{
          bar.style.background = 'rgba(239,68,68,0.1)';
          bar.style.border = '1px solid var(--danger)';
          bar.style.color = 'var(--danger)';
          bar.textContent = '⚠️ Chưa có Cloudflare tunnel đang chạy. Hãy chạy CHAY_WEB.bat rồi bấm nút này lại.';
        }}
      }} catch(e) {{
        bar.style.background = 'rgba(239,68,68,0.1)';
        bar.style.border = '1px solid var(--danger)';
        bar.style.color = 'var(--danger)';
        bar.textContent = '⚠️ Không thể kiểm tra tunnel. Dùng link Wi-Fi LAN bên cạnh để kết nối nội bộ.';
      }}
    }}

    async function loadQrCatalog() {{
      try {{
        const res = await fetch('/api/v1/qr-catalog?limit=150');
        if (!res.ok) return;
        const data = await res.json();
        allCatalogItems = data.items || [];
        // Populate customer dropdown
        const comps = Array.from(new Set(allCatalogItems.map(x => x.company).filter(Boolean))).sort();
        const compFilter = document.getElementById('qr-comp-filter');
        compFilter.innerHTML = '<option value="">Tất cả khách hàng (' + comps.length + ')</option>' +
          comps.map(c => `<option value="${{c}}">${{c}}</option>`).join('');
        filterQrCatalog();
      }} catch(e) {{}}
    }}

    function filterQrCatalog() {{
      const query = (document.getElementById('qr-search-input').value || '').trim().toLowerCase();
      const comp = (document.getElementById('qr-comp-filter').value || '').trim().toLowerCase();
      const filtered = allCatalogItems.filter(item => {{
        const matchQuery = !query ||
          item.part_name.toLowerCase().includes(query) ||
          item.product_code.toLowerCase().includes(query) ||
          item.tracking_code.toLowerCase().includes(query);
        const matchComp = !comp || item.company.toLowerCase() === comp;
        return matchQuery && matchComp;
      }});
      renderCatalog(filtered);
    }}

    function renderCatalog(items) {{
      const c = document.getElementById('qr-catalog-container');
      if (!items.length) {{
        c.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-muted);grid-column:1/-1;">Không tìm thấy chi tiết nào phù hợp bộ lọc.</div>';
        return;
      }}
      c.innerHTML = items.map(it => {{
        const testLink = '/tracking/mobile?qr=' + encodeURIComponent(it.qr_payload);
        return `
          <div class="qr-label-card">
            <div class="qr-card-top">
              <span class="qr-card-comp">${{it.company}}</span>
              <span class="qr-card-qty">${{it.quantity}} ${{it.unit}}</span>
            </div>
            <div class="qr-card-title">${{it.part_name}}</div>
            <div class="qr-card-body">
              <div class="qr-card-img">
                <img src="${{it.qr_data_uri}}" alt="QR">
              </div>
              <div class="qr-card-meta">
                <div>Mã SP: <b>${{it.product_code}}</b></div>
                <div>Tracking: <b>${{it.tracking_code}}</b></div>
                <div>Vật liệu: <b>${{it.material || '—'}}</b></div>
                <div>Quy cách: <b>${{it.size || '—'}}</b></div>
              </div>
            </div>
            <div class="qr-card-actions">
              <a href="${{testLink}}" target="_blank" class="btn btn-primary btn-sm" style="flex:1;">⚡ Quét Test</a>
              <button onclick="copySingleCardToExcel('${{it.tracking_code}}')" class="btn btn-outline btn-sm" title="Sao chép dòng dạng Excel (TSV)">📋 Copy</button>
              <button onclick="printSingleLabel('${{it.tracking_code}}')" class="btn btn-outline btn-sm">🖨️ In</button>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function copySingleCardToExcel(trackingCode) {{
      const it = allCatalogItems.find(x => x.tracking_code === trackingCode);
      if (!it) return;
      const headers = ['Mã Tracking', 'Mã Sản Phẩm', 'Tên Chi Tiết', 'Khách Hàng', 'Số Lượng', 'Đơn Vị', 'Vật Liệu', 'Quy Cách', 'Xử Lý Bề Mặt', 'Hạn Giao', 'Trạng Thái'];
      const row = [
        it.tracking_code, it.product_code, it.part_name, it.company,
        it.quantity, it.unit, it.material || '', it.size || '',
        it.surface_treatment || '', it.delivery_date || '', it.status
      ];
      const tsv = headers.join('\\t') + '\\r\\n' + row.join('\\t');
      navigator.clipboard.writeText(tsv).then(() => {{
        const t = document.getElementById('toast');
        t.textContent = `Đã copy chi tiết ${{it.part_name}} (${{it.tracking_code}}) dạng bảng Excel!`;
        t.style.display = 'block';
        setTimeout(() => {{ t.style.display = 'none'; }}, 2200);
      }});
    }}

    function copyCatalogToExcel() {{
      const query = (document.getElementById('qr-search-input').value || '').trim().toLowerCase();
      const comp = (document.getElementById('qr-comp-filter').value || '').trim().toLowerCase();
      const filtered = allCatalogItems.filter(item => {{
        const matchQuery = !query ||
          item.part_name.toLowerCase().includes(query) ||
          item.product_code.toLowerCase().includes(query) ||
          item.tracking_code.toLowerCase().includes(query);
        const matchComp = !comp || item.company.toLowerCase() === comp;
        return matchQuery && matchComp;
      }});
      if (!filtered.length) return alert('Không có chi tiết nào để sao chép.');
      const headers = ['Mã Tracking', 'Mã Sản Phẩm', 'Tên Chi Tiết', 'Khách Hàng', 'Số Lượng', 'Đơn Vị', 'Vật Liệu', 'Quy Cách', 'Xử Lý Bề Mặt', 'Hạn Giao', 'Trạng Thái'];
      const tsvLines = [headers.join('\\t')];
      filtered.forEach(it => {{
        tsvLines.push([
          it.tracking_code, it.product_code, it.part_name, it.company,
          it.quantity, it.unit, it.material || '', it.size || '',
          it.surface_treatment || '', it.delivery_date || '', it.status
        ].join('\\t'));
      }});
      const tsv = tsvLines.join('\\r\\n');
      navigator.clipboard.writeText(tsv).then(() => {{
        const t = document.getElementById('toast');
        t.textContent = `Đã copy ${{filtered.length}} chi tiết dạng bảng! Hãy mở Excel và bấm Ctrl+V.`;
        t.style.display = 'block';
        setTimeout(() => {{ t.style.display = 'none'; }}, 2800);
      }});
    }}

    function copyFeedToExcel() {{
      const rows = Array.from(document.querySelectorAll('#feed-tbody tr'));
      if (!rows.length) return alert('Không có dữ liệu tiến độ để sao chép.');
      const headers = ['Thời Gian', 'Nhân Sự', 'Chi Tiết Sản Phẩm', 'Công Đoạn / Thao Tác', 'Số Lượng', 'Ghi Chú'];
      const tsvLines = [headers.join('\\t')];
      rows.forEach(r => {{
        const cells = Array.from(r.querySelectorAll('td'));
        if (cells.length >= 6) {{
          const line = cells.map(c => c.innerText.replace(/\\r?\\n|\\r/g, ' ').trim()).join('\\t');
          tsvLines.push(line);
        }}
      }});
      const tsv = tsvLines.join('\\r\\n');
      navigator.clipboard.writeText(tsv).then(() => {{
        const t = document.getElementById('toast');
        t.textContent = 'Đã copy toàn bộ bảng Live Feed! Bạn có thể dán (Ctrl+V) thẳng vào Excel.';
        t.style.display = 'block';
        setTimeout(() => {{ t.style.display = 'none'; }}, 2800);
      }});
    }}

    function printSingleLabel(trackingCode) {{
      const item = allCatalogItems.find(x => x.tracking_code === trackingCode);
      if (!item) return;
      const printArea = document.getElementById('printable-area');
      printArea.innerHTML = `
        <div class="print-label">
          <img src="${{item.qr_data_uri}}">
          <div class="print-label-info">
            <div style="font-weight:900;font-size:13pt;border-bottom:1px solid #000;margin-bottom:4px;">${{item.part_name}}</div>
            <div><b>Khách hàng:</b> ${{item.company}}</div>
            <div><b>Mã SP:</b> ${{item.product_code}} · <b>Tracking:</b> ${{item.tracking_code}}</div>
            <div><b>Số lượng:</b> ${{item.quantity}} ${{item.unit}}</div>
            <div><b>Vật liệu:</b> ${{item.material || '—'}} · <b>Quy cách:</b> ${{item.size || '—'}}</div>
          </div>
        </div>
      `;
      window.print();
    }}

    function printLabels() {{
      const query = (document.getElementById('qr-search-input').value || '').trim().toLowerCase();
      const comp = (document.getElementById('qr-comp-filter').value || '').trim().toLowerCase();
      const filtered = allCatalogItems.filter(item => {{
        const matchQuery = !query ||
          item.part_name.toLowerCase().includes(query) ||
          item.product_code.toLowerCase().includes(query) ||
          item.tracking_code.toLowerCase().includes(query);
        const matchComp = !comp || item.company.toLowerCase() === comp;
        return matchQuery && matchComp;
      }});
      if (!filtered.length) return alert('Không có nhãn nào để in');
      const printArea = document.getElementById('printable-area');
      printArea.innerHTML = filtered.map(item => `
        <div class="print-label">
          <img src="${{item.qr_data_uri}}">
          <div class="print-label-info">
            <div style="font-weight:900;font-size:12pt;border-bottom:1px solid #000;margin-bottom:3px;">${{item.part_name}}</div>
            <div><b>Khách hàng:</b> ${{item.company}}</div>
            <div><b>Mã SP:</b> ${{item.product_code}} · <b>Tracking:</b> ${{item.tracking_code}}</div>
            <div><b>Số lượng:</b> ${{item.quantity}} ${{item.unit}}</div>
            <div><b>Vật liệu:</b> ${{item.material || '—'}}</div>
          </div>
        </div>
      `).join('');
      window.print();
    }}

{_SS_JS}
    let lastPastedItems = [];
    let pasteDebounceTimer = null;

    function debouncePastePreview() {{
      clearTimeout(pasteDebounceTimer);
      pasteDebounceTimer = setTimeout(previewPastedExcel, 600);
    }}

    async function readFromClipboard() {{
      try {{
        const text = await navigator.clipboard.readText();
        if (!text || !text.trim()) {{
          return alert('Bộ nhớ tạm (Clipboard) đang trống. Hãy bôi đen và copy các ô trong Excel trước.');
        }}
        document.getElementById('excel-paste-input').value = text;
        previewPastedExcel();
      }} catch(err) {{
        alert('Trình duyệt chưa cấp quyền đọc Clipboard: ' + err.message + '. Bạn có thể nhấp chuột vào ô và bấm Ctrl+V.');
      }}
    }}

    function fillSamplePaste() {{
      const sample = `Company\\tPart Name\\tQuantity\\tUnit\\tMaterial\\tSurface treatment\\tSize\\tPrice
CIT\\tTRỤC DẪN HƯỚNG D30\\t15\\tEA\\tS45C\\tMạ Crom\\tD30x450mm\\t320000
CIT\\tĐẾ GÁ BƠM THỦY LỰC\\t5\\tEA\\tA6061\\tAnodized Đen\\t220x150x30\\t850000
QCM\\tBẠC TRƯỢT TỰ BÔI TRƠN\\t40\\tPCS\\tĐồng Thau\\t—\\tID20xOD32x40\\t140000`;
      document.getElementById('excel-paste-input').value = sample;
      previewPastedExcel();
    }}

    function clearPasteArea() {{
      document.getElementById('excel-paste-input').value = '';
      document.getElementById('paste-status').style.display = 'none';
      document.getElementById('paste-preview-wrap').style.display = 'none';
      lastPastedItems = [];
    }}

    async function previewPastedExcel() {{
      const tsv = (document.getElementById('excel-paste-input').value || '').trim();
      const status = document.getElementById('paste-status');
      const wrap = document.getElementById('paste-preview-wrap');
      const tbody = document.getElementById('paste-preview-tbody');
      if (!tsv) {{
        status.style.display = 'none';
        wrap.style.display = 'none';
        return;
      }}
      status.style.display = 'block';
      status.innerHTML = '<span style="color:var(--accent);">Đang phân tích cấu trúc các dòng và cột dữ liệu...</span>';
      try {{
        const res = await fetch('/api/v1/excel/paste-preview', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{tsv: tsv}})
        }});
        if (!res.ok) {{
          const err = await res.json();
          status.innerHTML = `<span style="color:var(--danger);">Lỗi: ${{err.detail || 'Không thể bóc tách dữ liệu dán'}}</span>`;
          wrap.style.display = 'none';
          return;
        }}
        const data = await res.json();
        lastPastedItems = data.items || [];
        status.innerHTML = `<span style="color:var(--success);font-weight:700;">✅ Nhận diện thành công ${{data.total_items}} chi tiết từ Excel (Tổng SL: ${{data.total_quantity}}, Khách hàng: ${{data.companies.join(', ') || 'SHL'}})</span>`;
        wrap.style.display = 'block';
        tbody.innerHTML = lastPastedItems.map(it => `
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
            <td style="padding: 8px 10px;">${{it.row_index}}</td>
            <td style="padding: 8px 10px;"><b>${{it.company}}</b></td>
            <td style="padding: 8px 10px;">${{it.part_name}}</td>
            <td style="padding: 8px 10px;"><b>${{it.quantity}}</b></td>
            <td style="padding: 8px 10px;">${{it.unit}}</td>
            <td style="padding: 8px 10px;">${{it.material || '—'}}</td>
            <td style="padding: 8px 10px;">${{it.surface_treatment || '—'}}</td>
            <td style="padding: 8px 10px;">${{it.size || '—'}}</td>
            <td style="padding: 8px 10px;">${{it.price ? it.price.toLocaleString('vi-VN') + ' đ' : '—'}}</td>
          </tr>
        `).join('');
      }} catch(e) {{
        status.innerHTML = `<span style="color:var(--danger);">Lỗi kết nối: ${{e.message}}</span>`;
      }}
    }}

    async function importPastedExcel() {{
      const tsv = (document.getElementById('excel-paste-input').value || '').trim();
      const status = document.getElementById('paste-status');
      if (!tsv) return alert('Vui lòng dán nội dung từ Excel vào ô trước khi nạp.');
      if (!confirm('Bạn có chắc chắn muốn nạp các chi tiết đã dán vào cơ sở dữ liệu và tự động sinh mã QR không?')) return;
      status.style.display = 'block';
      status.innerHTML = '<span style="color:var(--accent);">Đang nạp vào cơ sở dữ liệu và cấp mã QR...</span>';
      try {{
        const res = await fetch('/api/v1/excel/paste-import', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{tsv: tsv, po_prefix: 'PO-DAN'}})
        }});
        if (!res.ok) {{
          const err = await res.json();
          status.innerHTML = `<span style="color:var(--danger);">Lỗi: ${{err.detail || 'Không thể nạp dữ liệu'}}</span>`;
          return;
        }}
        const data = await res.json();
        status.innerHTML = `<span style="color:var(--success);font-weight:700;">🎉 Thành công: Đã tạo ${{data.imported_products}} sản phẩm và cấp ${{data.imported_tracking_items}} mã QR tracking!</span>`;
        setTimeout(() => {{ location.reload(); }}, 1800);
      }} catch(e) {{
        status.innerHTML = `<span style="color:var(--danger);">Lỗi kết nối: ${{e.message}}</span>`;
      }}
    }}

    function copyPreviewToExcel() {{
      if (!lastPastedItems.length) return alert('Không có dữ liệu xem trước để sao chép.');
      const headers = ['Dòng', 'Khách Hàng', 'Tên Chi Tiết', 'Số Lượng', 'Đơn Vị', 'Vật Liệu', 'Xử Lý Bề Mặt', 'Kích Thước', 'Đơn Giá'];
      const tsvLines = [headers.join('\\t')];
      lastPastedItems.forEach(it => {{
        tsvLines.push([
          it.row_index, it.company, it.part_name, it.quantity, it.unit,
          it.material || '', it.surface_treatment || '', it.size || '', it.price || ''
        ].join('\\t'));
      }});
      navigator.clipboard.writeText(tsvLines.join('\\r\\n')).then(() => {{
        const t = document.getElementById('toast');
        t.textContent = 'Đã copy bảng xem trước sang clipboard (sẵn sàng dán vào Excel)!';
        t.style.display = 'block';
        setTimeout(() => {{ t.style.display = 'none'; }}, 2200);
      }});
    }}

    async function initExcelFiles() {{
      try {{
        const res = await fetch('/api/v1/excel/files');
        if (!res.ok) return;
        const data = await res.json();
        excelFilesData = data.files || [];
        const select = document.getElementById('excel-file-select');
        if (!select) return;
        select.innerHTML = excelFilesData.map(f => `<option value="${{f.filename}}">${{f.filename}} (${{f.sheets_count}} sheets)</option>`).join('');
        onFileSelectChange();
      }} catch(e) {{}}
    }}

    function onFileSelectChange() {{
      const fselect = document.getElementById('excel-file-select');
      const sselect = document.getElementById('excel-sheet-select');
      if (!fselect || !sselect) return;
      const file = excelFilesData.find(f => f.filename === fselect.value);
      if (file && file.sheets && file.sheets.length > 0) {{
        sselect.innerHTML = file.sheets.map(s => `<option value="${{s}}">${{s}}</option>`).join('');
      }} else {{
        sselect.innerHTML = '<option value="">(Không có sheet)</option>';
      }}
    }}

    async function loadExcelPreview() {{
      const fn = document.getElementById('excel-file-select').value;
      const sh = document.getElementById('excel-sheet-select').value;
      const status = document.getElementById('excel-status');
      const wrap = document.getElementById('excel-preview-wrap');
      const tbody = document.getElementById('excel-preview-tbody');
      status.style.display = 'block';
      status.innerHTML = '<span style="color:var(--accent);">Đang đọc dữ liệu từ tệp...</span>';
      try {{
        const res = await fetch('/api/v1/excel/preview', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{filename: fn, sheet: sh}})
        }});
        if (!res.ok) {{
          const err = await res.json();
          status.innerHTML = `<span style="color:var(--danger);">Lỗi: ${{err.detail || 'Không thể đọc'}}</span>`;
          return;
        }}
        const data = await res.json();
        status.innerHTML = `<span style="color:var(--success);font-weight:700;">Tìm thấy ${{data.total_items}} chi tiết hợp lệ (Tổng SL: ${{data.total_quantity}}, Khách hàng: ${{data.companies.join(', ')}})</span>`;
        wrap.style.display = 'block';
        tbody.innerHTML = (data.items || []).map(it => `
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
            <td style="padding: 8px 10px;">${{it.row_index}}</td>
            <td style="padding: 8px 10px;"><b>${{it.company}}</b></td>
            <td style="padding: 8px 10px;">${{it.part_name}}</td>
            <td style="padding: 8px 10px;"><b>${{it.quantity}}</b></td>
            <td style="padding: 8px 10px;">${{it.unit}}</td>
            <td style="padding: 8px 10px;">${{it.material || '—'}}</td>
            <td style="padding: 8px 10px;">${{it.surface_treatment || '—'}}</td>
            <td style="padding: 8px 10px;">${{it.size || '—'}}</td>
            <td style="padding: 8px 10px;">${{it.price ? it.price.toLocaleString('vi-VN') + ' đ' : '—'}}</td>
          </tr>
        `).join('');
      }} catch(e) {{
        status.innerHTML = `<span style="color:var(--danger);">Lỗi kết nối: ${{e.message}}</span>`;
      }}
    }}

    async function doExcelImport() {{
      const fn = document.getElementById('excel-file-select').value;
      const sh = document.getElementById('excel-sheet-select').value;
      const status = document.getElementById('excel-status');
      if (!confirm(`Bạn có chắc chắn muốn nạp toàn bộ chi tiết từ sheet "${{sh}}" vào cơ sở dữ liệu và phát hành mã QR không?`)) return;
      status.style.display = 'block';
      status.innerHTML = '<span style="color:var(--accent);">Đang nhập dữ liệu và cấp mã QR...</span>';
      try {{
        const res = await fetch('/api/v1/excel/import', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{filename: fn, sheet: sh}})
        }});
        if (!res.ok) {{
          const err = await res.json();
          status.innerHTML = `<span style="color:var(--danger);">Lỗi: ${{err.detail || 'Không thể nhập'}}</span>`;
          return;
        }}
        const data = await res.json();
        status.innerHTML = `<span style="color:var(--success);font-weight:700;">✅ Thành công: Đã nhập ${{data.imported_products}} sản phẩm và cấp ${{data.imported_tracking_items}} mã QR tracking!</span>`;
        setTimeout(() => {{ location.reload(); }}, 1800);
      }} catch(e) {{
        status.innerHTML = `<span style="color:var(--danger);">Lỗi kết nối: ${{e.message}}</span>`;
      }}
    }}

    function initWebSocket() {{
      try {{
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(proto + '//' + location.host + '/ws/live');
        ws.onmessage = () => {{
          autoRefreshFeed();
        }};
        ws.onclose = () => {{ setTimeout(initWebSocket, 4000); }};
      }} catch(e) {{}}
    }}

    initExcelFiles();
    initWebSocket();
    setInterval(autoRefreshFeed, 3000);
  </script>
</body>
</html>
"""
    return html


def portal_page() -> HTMLResponse:
    return HTMLResponse(render_portal_html())
