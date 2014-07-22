#!/bin/bash
set -e
set -x

cd "$(dirname "$0")"

# Script to bootstrap the 'wheel' wheel from deps.pyl, You only need to run
# this when upgrading the wheel wheel in deps.pyl, or when initializing the
# google storage bucket from scratch.

./bootstrap.py BUILD_ENV

. ./BUILD_ENV/bin/activate

read -r -d '' PROG <<EOF || true
import bootstrap
print bootstrap.read_deps('deps.pyl')['wheel']['gs']
EOF
SHA=$(echo "$PROG" | python -)
echo $SHA

pip install wheel "https://storage.googleapis.com/chrome-python-wheelhouse/sources/$SHA"

rm -rf wheelhouse
mkdir wheelhouse

python - <<EOF
import build_deps
import bootstrap
build = bootstrap.read_deps('deps.pyl')['wheel']['build']
build_deps.clear_wheelhouse()
build_deps.process_gs('wheel', '$SHA', build)
build_deps.push_wheelhouse()
EOF
