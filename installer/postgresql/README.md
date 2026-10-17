# PostgreSQL Offline Installer

Place the verified PostgreSQL Windows installer in this directory before creating a Server Tool release.

- File: `postgresql-17.11-4-windows-x64.exe`
- Source: PostgreSQL 17.11-4 Windows x64 package listed by the official Windows Package Manager manifest
- SHA-256: `c9828fd3a4daebbeeace19bec2de5f38d73c047fce47278148b525cfbe28a5e4`

The Server Tool verifies this checksum before opening the local installer. The installer file is intentionally not tracked in Git, but must be included in the offline release folder.
