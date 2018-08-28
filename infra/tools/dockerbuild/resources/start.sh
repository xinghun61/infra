#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Export all the cross-compile stuff
set -a
. /install-util.sh 2>/dev/null
set +x
set +a

fix_env_paths() {
  # for each line like `VAR=VALUE` in printenv
  local line=""
  while read line; do
    # i.e. `var, value = line.split('=', 1)`
    local var="${line%%=*}"
    local value="${line#*=}"
    if [[ $var == DOCKERBUILD_* ]]; then
      local target=""                    # the envvar we plan to modify
      value="$(base64 -id <<<"$value")"  # decode the value as base64
      if [[ $var == DOCKERBUILD_APPEND_* ]]; then
        target=${var#DOCKERBUILD_APPEND_}
        value="${!target}${value:+:}${value}"
      elif [[ $var == DOCKERBUILD_PREPEND_* ]]; then
        target=${var#DOCKERBUILD_PREPEND_}
        value="${value}${value:+:}${!target}"
      elif [[ $var == DOCKERBUILD_SET_* ]]; then
        target=${var#DOCKERBUILD_SET_}
      fi
      export $target="$value"
    fi
  done < <(printenv)
}

fix_env_paths
"$@"
