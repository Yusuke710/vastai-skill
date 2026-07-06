---
name: vastai-gpu
description: Rent a GPU on vast.ai, run experiments on it over SSH/rsync, pull artifacts back, and destroy it. Use when a task needs a GPU (training, CUDA, large-model inference).
---

# Run GPU experiments on vast.ai

You rent a GPU instance with the native `vastai` CLI, wait for it with `vastai-connect`
(which writes an SSH alias), then work with plain `ssh`/`rsync`. Money is spent per hour
from the moment an instance is created until it is **destroyed**. Never leave one behind.

## Prerequisites (check once)

```bash
vastai show instances --raw   # errors if vastai isn't installed or the API key isn't set
```

If missing, ask user to registered public SSH key at https://cloud.vast.ai/manage-keys/) and get vast ai api key. 
Run `uv tool install vastai && vastai set api-key <key>` and `uv tool install git+https://github.com/Yusuke710/vastai-connect.git` to install required software to run this skill. 

## 1. Find and rent

```bash
# Cheapest matching offers first. GPU names use underscores: RTX_3060, RTX_4090, A100_SXM4...
vastai search offers 'gpu_name=RTX_3060 num_gpus=1 reliability>0.98 dph<0.45' -o 'dph' --raw
```

Pick the cheapest offer's `id` and note its `dph_total` ($/hr). Sanity-check the price against
what the task deserves before renting. Then:

```bash
vastai create instance <offer_id> --image vastai/pytorch:latest --disk 30 --ssh --raw
# → {"success": true, "new_contract": <instance_id>}
```

- `--disk` cannot be resized later; size it for datasets + checkpoints.
- **Image choice:** default to `vastai/pytorch:latest`. Its CUDA base layers are cached on
most vast.ai hosts (boot-to-SSH ≈ 2–3 min). Alternatives only when justified.

If running more than one instance, label each so `vastai show instances` stays legible:

```bash
vastai label instance <instance_id> exp1
```

## 2. Wait until reachable

```bash
vastai-connect <instance_id>  --alias vast-gpu # blocks until SSH works; makes `ssh vast-gpu` usable
# → {"instance_id": ..., "ssh_alias": "vast-gpu", ...}
```

Use `--alias vast-<name>` when running several instances. Typical wait is 1–3 minutes.
On timeout (5 min default) or any stall later (crawling downloads, broken SSH auth), destroy and rent a different offer. Re-renting beats debugging. Cheap consumer hosts are a lottery and Datacenter GPUs (A100/H100) are usually more reliable.

## 3. Work over plain ssh/rsync

```bash
# Sync code (gitignore-filtered so .venv/data/checkpoints don't cross the wire)
rsync -az --filter=':- .gitignore' ./ vast-gpu:/workspace/proj/

# Install dependencies
ssh vast-gpu 'cd /workspace/proj && uv sync'

ssh vast-gpu 'cd /workspace/proj && uv run python train.py'

# Iterate: edit locally, re-sync (delta = ~1s), re-run
```

A GPU-verify one-liner after `uv sync — uv run python -c "import torch; torch.randn(1, device='cuda')"` — one cheap command that catches both hard-fail modes we hit (old driver → silent CPU fallback; old GPU → no kernel image) before any money is spent on a long run.

**Long jobs** (anything that could outlive a shell timeout):

```bash
# 1. Launch detached with an exit-code sentinel. nohup means the job survives SSH
#    drops and your session ending; job.exit records success (0) vs crash.
ssh vast-gpu 'cd /workspace/proj && rm -f job.exit && nohup bash -c \
  "uv run python train.py; echo \$? > job.exit" > train.log 2>&1 & echo started'

# 2. Start a blocking waiter as a background task in your harness — it exits the
#    moment the job finishes and reports the exit code (push, not poll):
ssh -o ServerAliveInterval=30 vast-gpu \
  'until [ -f /workspace/proj/job.exit ]; do sleep 15; done; \
   echo "exit=$(cat /workspace/proj/job.exit)"; tail -5 /workspace/proj/train.log'

# Check training progress anytime while waiting:
ssh vast-gpu 'tail -n 50 /workspace/proj/train.log'
```

If the waiter dies (SSH proxy hiccup), the sentinel file is still there — just rerun it.
Don't run training as a plain ssh command without nohup: if the connection drops, the
job dies with it.

**Before destroying:** the user may want to keep artifacts (model weights, logs, results)
that only exist on the instance. Check with the user, then transfer anything worth keeping —
e.g. `rsync -az vast-gpu:/workspace/proj/outputs/ ./outputs/`.

## 4. Destroy the instance

```bash
vastai destroy instance <instance_id>
vastai show instances --raw              # verify it's gone; [] means nothing is billing
```

- **Destroy, never `stop`** — stopped instances still bill storage and may be unable to restart.
- If you intentionally leave an instance running (e.g. a long training job), tell the user
  explicitly: instance id, $/hr, and how to destroy it.
