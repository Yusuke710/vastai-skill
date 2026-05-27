# vastai-connect

CLI wrapper for [Vast.ai](https://vast.ai) that simplifies GPU rental workflow. One command to search GPU, rent, ssh, then destroy the instance afterward.

## Installation

```bash
# Install vastai CLI first
uv tool install vastai
vastai set api-key <Enter your API key from https://cloud.vast.ai/manage-keys/>

# Install vastai-connect
uv tool install git+https://github.com/Yusuke710/vastai-connect.git

# Update to latest version
uv tool upgrade vastai-connect
```

## SSH Key Setup

Add your SSH public key to Vast.ai so you can connect to instances:

1. Copy your public key: `cat ~/.ssh/<your public key>.pub` or generate your own.
2. Go to https://cloud.vast.ai/manage-keys/ → SSH Keys section
3. Paste your public key and save

## Usage

```bash
vastai-connect
```

This will:
1. Show available GPU instances (arrow key selection)
2. Create the selected instance
3. Wait for it to be ready
4. SSH into the instance
5. On exit, prompt to destroy the instance (default: yes)

### Environment Variable Overrides

Override config without editing the file:

```bash
# Use VS Code instead of CLI
VAST_MODE=vscode vastai-connect

# Use Cursor instead of CLI
VAST_MODE=cursor vastai-connect

# Set disk size in GB (default: 10GB, cannot be resized after creation)
VAST_DISK=100 vastai-connect

# Combine options
VAST_MODE=vscode VAST_DISK=200 vastai-connect
```

## Configuration

The config file is bundled with the package. To find and edit it:

```bash
# Find config location
uv tool dir
# Then edit: <tool_dir>/vastai-connect/lib/python3.x/site-packages/vastai_connect/default_config.yaml
```


## What gets installed on the instance

Each instance [runs a startup script](src/vastai_connect/onstart.sh) that installs:
- [Claude Code](https://claude.ai/code)
- [Codex](https://chatgpt.com/codex)

## License 
MIT
