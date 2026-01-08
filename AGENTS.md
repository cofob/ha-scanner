# Project Overview

Libinsane Scanner is a Home Assistant add-on that scans documents using libinsane/SANE, delivers scans via Telegram, and accepts automation commands through Supervisor STDIN. It runs under s6-overlay and uses a stdin bridge to forward `hassio.addon_stdin` input to the scanner daemon.

## Important Files

- `app/main.py`: Core scanner daemon, Telegram bot, STDIN command handling, and Home Assistant API calls.
- `app/stdin_bridge.py`: Reads Supervisor STDIN and forwards messages to the daemon via `/tmp/ha_stdin.sock`.
- `app/config.py`: Loads add-on options from `/data/options.json`.
- `config.yaml`: Add-on metadata and options schema; version is the release source of truth.
- `CHANGELOG.md`: Release notes for each version.
- `DOCS.md`: User-facing usage docs (commands, automation examples, storage).
- `rootfs/usr/local/bin/run.sh`: Container CMD; runs the stdin bridge.
- `rootfs/etc/services.d/scanner/run`: s6 service that runs the scanner daemon.
- `Dockerfile`: Build dependencies and container setup.

## Release Process

1) Update version in `config.yaml`.
2) Add a release entry in `CHANGELOG.md`.
3) Commit changes (include code + version + changelog).
4) Tag the release with `vX.Y.Z`.
5) Push the commit and tag.

Example (single command):

```bash
git add <files> && git commit -m "Release X.Y.Z" && git tag vX.Y.Z && git push origin main && git push origin vX.Y.Z
```
