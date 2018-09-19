#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

./configure.py --bootstrap
if [[ $PLATFORM == windows* ]]; then
  cp ninja.exe "$PREFIX"
else
  cp ninja "$PREFIX"
fi
