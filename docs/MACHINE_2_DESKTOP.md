# Machine 2 Desktop

## Start

1. Copy the HMS QR Desktop release folder to Machine 2.
2. Run `TAO_SHORTCUT_DESKTOP.bat` once to create the `HMS QR Desktop` shortcut on the current Windows Desktop.
3. Open the shortcut, or run `CHAY_DESKTOP.bat` directly.
4. Desktop automatically checks a previously verified Server, then discovers Machine 1 on the Private LAN.
5. If discovery fails, use `TÌM SERVER LAN` or enter the Machine 1 URL, for example `http://192.168.2.15:8010`.
6. Sign in with the assigned HMS QR account. The initial setup account is `admin` / `admin`; change it after initial acceptance.

## First-Run Checks

- The status bar must show `Desktop LAN 1.0`, `SERVER: ĐÃ KẾT NỐI`, the Machine 1 URL, and the signed-in role.
- The launcher must find Python 3.14 x64; it stops with a clear message if that runtime is unavailable.
- Use `KIỂM TRA KẾT NỐI` before entering data if the LAN state is uncertain.
- Desktop must not ask for a database address, storage folder, token, or Server filesystem path.
- If the connection fails, verify Machine 1 is running, both machines use the Private LAN, and TCP `8010` / UDP `8011` are allowed on Machine 1.

## Acceptance Evidence

1. On the actual Machine 2, run `KIEM_TRA_MAY_2.bat` before `CHAY_DESKTOP.bat`.
2. Enter an assigned account only at the hidden password prompt. Do not pass credentials as command-line arguments or environment variables.
3. The required output begins `DAT:` and confirms UDP discovery, database readiness, authenticated login, and a bearer-authenticated Stage 2 read.
4. Run `CHAY_DESKTOP.bat` with no `HMS_QR_SERVER_URL` configured. Confirm the Desktop displays the discovered Machine 1 URL and signed-in role.
5. As `EDITOR`, create and view a dedicated acceptance customer/PO in Stage 2. As `VIEWER`, confirm create controls are disabled and a direct write is rejected by the Server.
6. Record the Machine 2 Windows username, date/time, discovered URL, account roles used, and only the `DAT:` result. Do not record credentials, tokens, or database details.

## Role Checks

- `ADMIN`: product, worksheet, file, and storage administration features.
- `EDITOR`: product, worksheet, and file operations permitted by the Server.
- `VIEWER`: read-only Product Master and files; Desktop disables change controls.
