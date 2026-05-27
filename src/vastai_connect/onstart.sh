#!/bin/bash
# Startup script for vast.ai instances

set -euo pipefail

if [ -s /opt/nvm/nvm.sh ]; then
    source /opt/nvm/nvm.sh
fi

if ! command -v npm >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs npm
fi

npm install -g @openai/codex@latest @anthropic-ai/claude-code@latest
