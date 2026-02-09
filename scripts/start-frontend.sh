#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../frontend"

npm_config_cache=../.npm-cache npm install
npm run dev
