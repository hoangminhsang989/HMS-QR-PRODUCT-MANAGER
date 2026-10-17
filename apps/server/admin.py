"""Server administration routes for accounts, display settings, and diagnostics."""

from __future__ import annotations

import socket

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from config.environments import AppConfig
from packages.application.server_auth import AuthenticationError, ServerAuthService, UserRole
from packages.persistence.database import DatabaseRuntime


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=0, max_length=512)


class AccountRequest(LoginRequest):
    role: UserRole


class AccountPatch(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    active: bool | None = None
    role: UserRole | None = None
    password: str | None = Field(default=None, min_length=0, max_length=512)


class SettingsRequest(BaseModel):
    site_title: str | None = Field(default=None, max_length=500)
    site_message: str | None = Field(default=None, max_length=500)


def _port_state(port: int) -> dict[str, object]:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return {"port": port, "state": "LISTENING", "guidance": "Dịch vụ đang lắng nghe cổng này."}
    except OSError:
        return {"port": port, "state": "UNREACHABLE", "guidance": "Khởi động lại dịch vụ server hoặc kiểm tra Windows Firewall cho cổng này."}


def _local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            return str(probe.getsockname()[0])
    except OSError:
        return "127.0.0.1"


def admin_page() -> HTMLResponse:
    return HTMLResponse("""<!doctype html><html lang='vi'><meta charset='utf-8'><title>HMS QR Server Admin</title>
<style>body{font:15px system-ui;max-width:960px;margin:32px auto;background:#f4f7f8;color:#102a35}section{background:#fff;padding:20px;margin:16px 0;border-radius:10px;box-shadow:0 1px 4px #ccd}input,select,button{padding:8px;margin:4px}button{background:#087f6b;color:#fff;border:0;border-radius:4px}pre{background:#122b39;color:#d9f5ed;padding:12px;overflow:auto}.bad{color:#b42318}</style>
<h1>HMS QR Server</h1><p>Quản trị tài khoản LAN, thông tin website và chẩn đoán kết nối.</p>
<section><h2>Đăng nhập quản trị</h2><input id='username' placeholder='Tên đăng nhập'><input id='password' type='password' placeholder='Mật khẩu'><button onclick='login()'>Đăng nhập</button><p id='login'></p></section>
<section><h2>Thông tin truy cập</h2><pre id='network'>Đăng nhập để xem trạng thái.</pre><button onclick='diagnostics()'>Kiểm tra lại</button></section>
<section><h2>Tài khoản LAN</h2><input id='new-name' placeholder='Tên đăng nhập'><input id='new-password' type='password' placeholder='Mật khẩu tối thiểu 3 ký tự, hoặc để trống khi server bật chế độ nội bộ'><select id='new-role'><option>EDITOR</option><option>VIEWER</option><option>ADMIN</option></select><button onclick='createAccount()'>Tạo tài khoản</button><pre id='accounts'></pre></section>
<section><h2>Thông tin website</h2><input id='site-title' placeholder='Tiêu đề website'><input id='site-message' placeholder='Thông báo hiển thị'><button onclick='saveSettings()'>Lưu</button><pre id='settings'></pre></section>
<script>let token='';const api='/admin-api';const headers=()=>({'Authorization':'Bearer '+token,'Content-Type':'application/json'});async function request(path,options={}){let r=await fetch(api+path,{...options,headers:{...headers(),...(options.headers||{})}});let b=await r.json();if(!r.ok)throw Error(b.detail?.message||b.detail||'Yêu cầu thất bại');return b}async function login(){try{let b=await request('/api/v1/auth/login',{method:'POST',body:JSON.stringify({username:document.getElementById('username').value,password:document.getElementById('password').value})});token=b.access_token;document.getElementById('login').innerText='Đã đăng nhập: '+b.username;await Promise.all([accounts(),diagnostics(),settings()])}catch(e){let el=document.getElementById('login');el.innerText=e.message;el.className='bad'}}async function accounts(){document.getElementById('accounts').innerText=JSON.stringify(await request('/api/v1/admin/accounts'),null,2)}async function createAccount(){try{await request('/api/v1/admin/accounts',{method:'POST',body:JSON.stringify({username:document.getElementById('new-name').value,password:document.getElementById('new-password').value,role:document.getElementById('new-role').value})});await accounts()}catch(e){document.getElementById('accounts').innerText=e.message}}async function diagnostics(){try{document.getElementById('network').innerText=JSON.stringify(await request('/api/v1/admin/diagnostics'),null,2)}catch(e){document.getElementById('network').innerText=e.message}}async function settings(){try{let b=await request('/api/v1/admin/settings');document.getElementById('site-title').value=b.site_title||'';document.getElementById('site-message').value=b.site_message||'';document.getElementById('settings').innerText=JSON.stringify(b,null,2)}catch(e){document.getElementById('settings').innerText=e.message}}async function saveSettings(){try{await request('/api/v1/admin/settings',{method:'PUT',body:JSON.stringify({site_title:document.getElementById('site-title').value,site_message:document.getElementById('site-message').value})});await settings()}catch(e){document.getElementById('settings').innerText=e.message}}</script></html>""")


def build_admin_api(config: AppConfig, runtime: DatabaseRuntime) -> FastAPI:
    api = FastAPI(title="HMS QR Server Administration", version="1.0")
    auth = ServerAuthService(runtime)

    def admin(authorization: str | None = Header(default=None)) -> dict[str, str]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, detail={"message": "Cần đăng nhập quản trị."})
        try:
            principal = auth.authenticate(authorization.removeprefix("Bearer ").strip())
        except AuthenticationError as exc:
            raise HTTPException(401, detail={"message": str(exc)}) from None
        if principal["role"] != UserRole.ADMIN.value:
            raise HTTPException(403, detail={"message": "Tài khoản không có quyền quản trị."})
        return principal

    @api.post("/api/v1/auth/login")
    def login(payload: LoginRequest):
        try:
            auth.bootstrap_admin()
            return auth.login(payload.username, payload.password)
        except (AuthenticationError, ValueError) as exc:
            raise HTTPException(401, detail={"message": str(exc)}) from None

    @api.get("/api/v1/admin/accounts")
    def accounts(_principal: dict[str, str] = Depends(admin)):
        return {"items": auth.list_accounts()}

    @api.post("/api/v1/admin/accounts")
    def create_account(payload: AccountRequest, _principal: dict[str, str] = Depends(admin)):
        try:
            return auth.create_account(payload.username, payload.password, payload.role.value)
        except ValueError as exc:
            raise HTTPException(422, detail={"message": str(exc)}) from None

    @api.patch("/api/v1/admin/accounts/{identifier}")
    def update_account(identifier: str, payload: AccountPatch, _principal: dict[str, str] = Depends(admin)):
        try:
            return auth.update_account(
                identifier,
                username=payload.username,
                active=payload.active,
                role=payload.role.value if payload.role else None,
                password=payload.password,
            )
        except ValueError as exc:
            raise HTTPException(422, detail={"message": str(exc)}) from None

    @api.get("/api/v1/admin/settings")
    def settings(_principal: dict[str, str] = Depends(admin)):
        return auth.settings()

    @api.put("/api/v1/admin/settings")
    def update_settings(payload: SettingsRequest, _principal: dict[str, str] = Depends(admin)):
        auth.update_settings(payload.model_dump(exclude_none=True))
        return auth.settings()

    @api.get("/api/v1/admin/diagnostics")
    def diagnostics(_principal: dict[str, str] = Depends(admin)):
        ip = _local_ip()
        return {
            "environment": config.environment.value,
            "database": runtime.readiness(),
            "lan_address": ip,
            "desktop_server_url": f"http://{ip}:8000",
            "admin_url": f"http://{ip}:8000/admin",
            "ports": [_port_state(8000)],
            "repair_policy": "Server does not stop other processes, alter firewall rules, or select a new port automatically. Apply the displayed guidance, then retry this check.",
        }

    return api


__all__ = ["admin_page", "build_admin_api"]
