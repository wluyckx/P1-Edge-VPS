# P1-Edge-VPS

HomeWizard P1 edge collector + VPS API stack.

## Hardened Repo Defaults

- Local agent metadata (`.claude/`) is now ignored.
- Secret scan gate added: `make secrets` (also included in `make check`).
- `.env` variants ignored by default, with `.env.example` explicitly allowed.

## Deploy Edge On HAOS

This repo now includes a Home Assistant add-on package at `p1_edge/`.

1. In Home Assistant: `Settings -> Add-ons -> Add-on Store -> Repositories`.
2. Add your repository URL.
3. Install `P1 Edge Daemon`.
4. Configure required options:
   - `hw_p1_host`
   - `hw_p1_token`
   - `vps_ingest_url` (must be `https://...`)
   - `vps_device_token`
5. Start add-on and check logs.

## Deploy VPS (SolarEdge-to-VPS Style)

Deployment files are in `vps/`:

- `vps/docker-compose.yml`
- `vps/Caddyfile`
- `vps/.env.example`

Steps:

1. Copy env template: `cp vps/.env.example vps/.env`
2. Set `DOMAIN`, `POSTGRES_PASSWORD`, `DEVICE_TOKENS` in `vps/.env`
3. Start stack:
   - `cd vps`
   - `docker compose up -d --build`
4. Verify:
   - `docker compose ps`
   - `curl -si http://127.0.0.1:8000/health` (inside VPS host)
   - `curl -si https://<DOMAIN>/v1/realtime?device_id=<id>`
