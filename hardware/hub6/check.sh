#!/bin/bash
# ERC, DRC with the schematic parity check, and the netlist tests.
# Reports go to build/. Fails if any check finds anything.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
kicad-cli sch erc --severity-all --exit-code-violations -o build/erc.rpt hub6.kicad_sch
kicad-cli pcb drc --schematic-parity --severity-all --exit-code-violations -o build/drc.rpt hub6.kicad_pcb
PYTHONPATH=/usr/lib/python3/dist-packages uv run -q --no-project --python /usr/bin/python3 --with pytest \
  python -m pytest -q -p no:cacheprovider -W ignore::DeprecationWarning test_hub6.py
