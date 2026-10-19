# Offline Server Release

Run `THIET_LAP_SERVER_1_CLICK.bat` on Machine 1. It requests the required Windows Administrator elevation automatically.

Desktop clients automatically discover a ready HMS QR Server on the Private LAN through UDP `8011`, then verify the API database readiness on TCP `8010`. The one-click setup opens both Private firewall rules; do not expose either port on Public networks.

The launcher installs Python 3.14 and HMS QR packages only from the bundled files. It then opens HMS QR Server Tool. In the Tool, select `THIET LAP SERVER 1 CLICK` to create the local production configuration at `D:\HMS-QR-PROD`, apply the embedded SQL engine migrations, generate DPAPI-protected credentials, and open the Private LAN Firewall rule for TCP 8010. No external database server is installed: the application embeds its own SQL engine.

The release must contain these unmodified artifacts:

- `installer/python/python-3.14.6-amd64.exe`, SHA-256 `14b3e9a710a3fcf0bd9b55ab6b60412bd91227563f813fc49040cabc0209e0bd`
- all wheels in `installer/wheels`
