#!/bin/bash

TOOLS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR=$TOOLS_DIR/..
cd "$APP_DIR/../.."
./test.py test "$APP_DIR" "$@"
