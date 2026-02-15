# P1 Edge Daemon (HAOS Add-on)

This add-on runs the P1 edge daemon for the P1-Edge-VPS pipeline.

## Install

1. In Home Assistant: Settings -> Add-ons -> Add-on Store -> menu -> Repositories.
2. Add this repository URL.
3. Install `P1 Edge Daemon`.
4. Configure options and start.

## Notes

- `spool_path` defaults to `/data/spool.db` (persistent add-on storage).
- Health file is written to `/data/health.json`.
- `vps_ingest_url` must be `https://...`.
