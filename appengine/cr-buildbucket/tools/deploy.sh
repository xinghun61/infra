#!/bin/sh

BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ $BRANCH != 'master' ]; then
  echo Deploy on master branch
  exit 1
fi

TOOLS_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
$TOOLS_DIR/gae.py upload -A cr-buildbucket -x