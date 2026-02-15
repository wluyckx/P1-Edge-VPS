#!/usr/bin/with-contenv bashio
set -e

export HW_P1_HOST="$(bashio::config 'hw_p1_host')"
export HW_P1_TOKEN="$(bashio::config 'hw_p1_token')"
export VPS_INGEST_URL="$(bashio::config 'vps_ingest_url')"
export VPS_DEVICE_TOKEN="$(bashio::config 'vps_device_token')"
export POLL_INTERVAL_S="$(bashio::config 'poll_interval_s')"
export BATCH_SIZE="$(bashio::config 'batch_size')"
export UPLOAD_INTERVAL_S="$(bashio::config 'upload_interval_s')"
export SPOOL_PATH="$(bashio::config 'spool_path')"

if bashio::config.has_value 'device_id'; then
  export DEVICE_ID="$(bashio::config 'device_id')"
fi

exec python -m edge.src.main
