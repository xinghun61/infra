# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of luci-py.git CI resources."""

load('//lib/build.star', 'build')
load('//lib/infra.star', 'infra')


infra.cq_group(
    name = 'luci-py cq',
    repo = 'https://chromium.googlesource.com/infra/luci/luci-py',
)

build.presubmit(
    name = 'luci-py-try-presubmit',
    cq_group = 'luci-py cq',
    repo_name = 'luci_py',
    os = 'Ubuntu-16.04',
    # The default 8-minute timeout is a problem for luci-py.
    # See https://crbug.com/917479 for context.
    timeout_s = 900,
    vpython_spec_path = '.vpython',
)
