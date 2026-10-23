#!/bin/bash
# ERC, DRC with the schematic parity check. Reports go to build/. Fails if any check finds anything.
# (A draft: no netlist tests yet.)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
kicad-cli sch erc --severity-all --exit-code-violations -o build/erc.rpt hub6_one.kicad_sch
kicad-cli pcb drc --schematic-parity --severity-all --exit-code-violations -o build/drc.rpt hub6_one.kicad_pcb
