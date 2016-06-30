#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/.."
cd "$DIR/../../"
./test.py test appengine/chrome_infra_packages "$@" --html-report "$DIR/.coverage"
