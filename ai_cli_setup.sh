#!/usr/bin/env bash
# WBS-AICli — Ubuntu 22.04/24.04 / Debian family. Root requires --allow-root.
set -euo pipefail
set +x
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ ! -x /usr/bin/python3 ]]; then
  printf '%s\n' '缺少系统 Python 3。请先安装：sudo apt-get update && sudo apt-get install python3' >&2
  exit 2
fi
if ! /usr/bin/python3 -B -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  printf '%s\n' '需要系统 Python 3.10 或更高版本；请使用 Ubuntu 22.04/24.04 的系统 Python。' >&2
  exit 2
fi
exec /usr/bin/python3 -B -I "$HERE/ai_cli_manager.py" "$@"
