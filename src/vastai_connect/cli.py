"""Wait for a rented vast.ai instance to be reachable, then wire up SSH access.

Renting is done directly with the native vastai CLI:
    vastai search offers 'gpu_name=RTX_3060 dph<0.15' -o 'dph' --raw
    vastai create instance <offer_id> --image vastai/pytorch:latest --disk 30 --ssh --raw
    vastai show instances --raw
    vastai destroy instance <instance_id>

This tool only covers the gap in between: polling until the instance is actually
running and SSH accepts connections, writing a Host alias to ~/.ssh/config, and
optionally opening VS Code/Cursor on it. On success it prints JSON to stdout.
"""

import argparse
import json
import sys

from .instance import (
    DEFAULT_ALIAS, get_ssh_host_port, log, open_ide,
    update_ssh_config_for_instance, wait_for_instance, wait_for_ssh,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="vastai-connect",
        description="Wait until a vast.ai instance is SSH-reachable and add a Host alias "
                    "to ~/.ssh/config. Rent/destroy instances with the vastai CLI itself.",
    )
    parser.add_argument("instance_id", type=int, help="Instance ID from `vastai create instance`")
    parser.add_argument("--alias", default=DEFAULT_ALIAS,
                        help=f"SSH config Host alias to write (default: {DEFAULT_ALIAS})")
    parser.add_argument("--ide", choices=("code", "cursor"),
                        help="Open this IDE on the instance once ready")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Seconds to wait for the instance to start (default: 300)")
    args = parser.parse_args()

    try:
        if not wait_for_instance(args.instance_id, args.timeout):
            log(f"Instance {args.instance_id} did not reach 'running' state. "
                f"Check: vastai show instances")
            return 1

        if not wait_for_ssh(args.instance_id):
            log("SSH did not become ready. Check your SSH key at https://cloud.vast.ai/manage-keys/")
            return 1

        update_ssh_config_for_instance(args.instance_id, args.alias)

        if args.ide:
            open_ide(args.ide, args.alias)

        user_host, port = get_ssh_host_port(args.instance_id)
        print(json.dumps({
            "instance_id": args.instance_id,
            "ssh_alias": args.alias,
            "ssh_host": user_host,
            "ssh_port": port,
        }))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        log(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
