#!/usr/bin/bash

set -euo pipefail

ROOT_FOLDER="$(cd "$(dirname "$0")/.." && pwd)"

fd -t f '^SKILL\.md$' $ROOT_FOLDER
