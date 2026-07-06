"""The glue vast.ai's own CLI doesn't provide: readiness waiting, SSH config, IDE launch.

Everything else (search offers, create, show, destroy) is done directly with `vastai`.
"""

import functools
import json
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_ALIAS = "vast-gpu"

# Status messages go to stderr so stdout can stay machine-readable
log = functools.partial(print, file=sys.stderr)


def get_ssh_host_port(instance_id: int) -> tuple[str, str]:
    """Return (user@host, port) for an instance, from `vastai ssh-url`."""
    result = subprocess.run(
        ["vastai", "ssh-url", str(instance_id)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to get SSH URL: {result.stderr}")

    ssh_url = result.stdout.strip()  # e.g. ssh://root@ssh6.vast.ai:17538
    if not ssh_url.startswith("ssh://"):
        raise RuntimeError(f"Unexpected ssh-url output: {ssh_url!r}")
    user_host, port = ssh_url.removeprefix("ssh://").rsplit(":", 1)
    return user_host, port


def get_ssh_command(instance_id: int) -> list[str]:
    """Get the SSH command for connecting to an instance."""
    user_host, port = get_ssh_host_port(instance_id)
    return ["ssh", "-p", port, user_host]


def wait_for_instance(instance_id: int, timeout: int = 300) -> bool:
    """Wait for instance to be running. Returns True when ready."""
    log(f"Waiting for instance {instance_id} to start...", end="", flush=True)
    start_time = time.time()

    while time.time() - start_time < timeout:
        result = subprocess.run(
            ["vastai", "show", "instances", "--raw"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            instances = json.loads(result.stdout)
            for instance in instances:
                if instance.get("id") == instance_id:
                    status = instance.get("actual_status", "")
                    if status == "running":
                        log(" Ready!")
                        return True

        log(".", end="", flush=True)
        time.sleep(5)

    log(" Timeout!")
    return False


def wait_for_ssh(instance_id: int, timeout: int = 180) -> bool:
    """Wait for SSH to be actually accessible. Returns True when ready."""
    log("Waiting for SSH to be ready...", end="", flush=True)
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            ssh_cmd = get_ssh_command(instance_id)
            result = subprocess.run(
                ssh_cmd + ["-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
                           "-o", "BatchMode=yes", "exit", "0"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                log(" Ready!")
                return True
            if "Permission denied" in result.stderr:
                log(" Authentication failed! Check your SSH key configuration.")
                return False
        except Exception:
            pass
        log(".", end="", flush=True)
        time.sleep(3)

    log(" Timeout!")
    return False


VASTAI_CONF = Path.home() / ".ssh" / "vastai.conf"
INCLUDE_LINE = "Include ~/.ssh/vastai.conf"


def _ensure_include() -> None:
    """One-time edit of ~/.ssh/config: include vastai.conf."""
    ssh_dir = VASTAI_CONF.parent
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    config = ssh_dir / "config"
    text = config.read_text() if config.exists() else ""
    if INCLUDE_LINE not in text:
        config.write_text(f"{INCLUDE_LINE}\n\n{text}")
        config.chmod(0o600)
        log(f"Added '{INCLUDE_LINE}' to {config}")


def update_ssh_config_for_instance(instance_id: int, alias: str = DEFAULT_ALIAS) -> None:
    """Write the instance's Host alias to ~/.ssh/vastai.conf (owned by this tool).

    ~/.ssh/config itself is only touched once, to add the Include line.
    """
    user_host, port = get_ssh_host_port(instance_id)
    user, host = user_host.split("@")

    # Whitespace in any value could inject extra config directives
    for name, val in [("alias", alias), ("host", host), ("port", port), ("user", user)]:
        if not val or any(c.isspace() for c in val):
            raise ValueError(f"Invalid SSH {name}: {val!r}")

    _ensure_include()

    # One block per alias: keep other aliases, replace this one
    old = VASTAI_CONF.read_text() if VASTAI_CONF.exists() else ""
    blocks = [b.strip() for b in old.split("\n\n") if b.strip()]
    blocks = [b for b in blocks if b.splitlines()[0] != f"Host {alias}"]
    blocks.append(
        f"Host {alias}\n"
        f"    HostName {host}\n"
        f"    Port {port}\n"
        f"    User {user}\n"
        f"    StrictHostKeyChecking accept-new"
    )
    VASTAI_CONF.write_text("\n\n".join(blocks) + "\n")
    VASTAI_CONF.chmod(0o600)

    log(f"SSH alias ready: ssh {alias}  ({VASTAI_CONF})")


def open_ide(ide_command: str, alias: str = DEFAULT_ALIAS) -> bool:
    """Open IDE with remote SSH connection. Returns True on success.

    Assumes update_ssh_config_for_instance() was already called.
    """
    # Use SSH config alias - VS Code reads port from config
    cmd = [ide_command, "--remote", f"ssh-remote+{alias}", "/root"]

    log(f"Opening {ide_command}: {' '.join(cmd)}")
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        log(f"Error: '{ide_command}' not found. Install it or add to PATH.")
        return False
