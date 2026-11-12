#!/bin/bash
# Demo: run the whole pipeline on the sample data.
set -e
cd "$(dirname "$0")"
python3 -m leadgen.cli demo "$@"
