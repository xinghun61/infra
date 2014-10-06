# -*- mode: shell-script -*-
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This is a bash configuration script that will configure your shell environment
# in the same way that infra wrapper scripts like run.py and test.py do.  That
# allows you to run unwrapped infra tool invocations directly from the shell
# prompt.  To use it, run `source virtualenv.bashrc` from anywhere inside your
# gclient root (you must specify the correct path to virtualenv.bashrc).

unset _testenv_gclient_root
unset _testenv_ae_root
unset _testenv_append_to_path
unset _testenv_prepend_to_path

_testenv_gclient_root=$PWD
while [ ! -f "$_testenv_gclient_root/.gclient" ] || \
    [ ! -d "$_testenv_gclient_root/google_appengine" ]; do
  _testenv_gclient_root=${_testenv_gclient_root%/*}
  if [ -z "$_testenv_gclient_root" ]; then
    echo "ERROR: Couldn't find the root of your checkout" 1>&2
    exit 1
  fi
done

_testenv_ae_root="$_testenv_gclient_root"/google_appengine

function _testenv_append_to_path() {
  for p in ${!1//:/ }; do
    if [ "$p" == "$2" ]; then
      echo "${!1}"
      return 0
    fi
  done
  if [ -z "${!1}" ]; then
    echo "$2"
  else
    echo "${!1}:$2"
  fi
  return 0
}

function _testenv_prepend_to_path() {
  for p in ${!1//:/ }; do
    if [ "$p" == "$2" ]; then
      echo "${!1}"
      return 0
    fi
  done
  if [ -z "${!1}" ]; then
    echo "$2"
  else
    echo "$2:${!1}"
  fi
  return 0
}
export PATH=$(\
    _testenv_prepend_to_path PATH "$_testenv_gclient_root/infra/ENV/bin")

export PYTHONPATH=$(_testenv_append_to_path PYTHONPATH \
    "$_testenv_gclient_root/infra")
for p in $(cat <<EOF | PYTHONPATH="$_testenv_ae_root" python
import os, wrapper_util
p = wrapper_util.Paths('$_testenv_ae_root')
p = p.script_paths('dev_appserver.py') + p.v2_extra_paths
print ' '.join(p)
EOF
); do
  export PYTHONPATH=$(_testenv_append_to_path PYTHONPATH "$p")
done

unset _testenv_gclient_root
unset _testenv_ae_root
unset _testenv_append_to_path
unset _testenv_prepend_to_path