#!/bin/bash
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# TODO(ukai): use html/template.
# it hangs in Execute, even if we use different delims,
# such as "{{||" and "||}}".
dir=$(cd $(dirname $0); pwd)
outdir=$dir/default/tmpl
mkdir -p $outdir || true
cd $dir/../third_party/trace-viewer/
./trace2html --output=$outdir/trace-viewer.html $dir/default/tmpl/dummy.json
