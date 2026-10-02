#!/bin/sh
set -eu
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3.11 or newer is needed to run Drishti.'
  exit 1
fi
if [ ! -f dist/index.html ]; then
  npm ci
  npm run build
fi
printf '\nOpen http://127.0.0.1:8765/ in your browser. Press Control+C to stop.\n\n'
exec python3 -m backend.server
