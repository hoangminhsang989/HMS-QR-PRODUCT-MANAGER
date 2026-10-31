import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apps.desktop.lan_diagnostic import run_check

creds = {}
for line in Path(r"C:\exchange\m1-creds.txt").read_text(encoding="utf-8").splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        creds[key.strip()] = value.strip()

try:
    server_url, role = run_check(username=creds["username"], password=creds["password"])
    print(f"ĐẤT: {server_url} role={role}")
except RuntimeError as exc:
    print(f"KHÔNG ĐẤT: {exc}")
