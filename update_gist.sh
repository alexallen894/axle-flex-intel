#!/bin/bash
# Runs at 6:50am daily — fetches Elexon data and pushes to Gist for remote agent to read
set -e

cd "$(dirname "$0")"
python3 fetch_data.py > /tmp/axle_latest_data.json 2>/tmp/axle_fetch.log
gh gist edit c4d9aea0c15c6c9dcafb2cc65381c09a -f latest_data.json /tmp/axle_latest_data.json
echo "$(date): Gist updated" >> /tmp/axle_fetch.log
