#!/bin/sh
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# goapp wrapper for chromium-build-stats.appspot.com
# - set GOPATH to ../third_party
#
# Usage:
#  $ cd default
#  $ ../goenv.sh goapp serve
#
dir=$(cd $(dirname $0); pwd)
go_appengine_dir=$dir/../../../go_appengine
third_party_dir=$dir/../third_party
export GOPATH=$third_party_dir
cmd=$1
shift
$go_appengine_dir/$cmd "$@"
