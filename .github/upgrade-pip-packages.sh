#!/bin/bash
set -euo pipefail

base="$(dirname "$0")"
python_minor_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

pip install --upgrade --force pip==24.0.0
pip install --upgrade --upgrade-strategy eager -r "$base/../python/requirements.txt"

pip install pipdeptree
pipdeptree --packages="$(sed -e "s/;.*//" -e "s/=.*//g" "$base/../python/requirements.txt" | paste -s -d ,)" --freeze > "$base/../python/requirements-$python_minor_version.txt"

git diff "$base/../python/requirements-$python_minor_version.txt"

