# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of luci-py.git CI resources."""

load('//lib/infra.star', 'infra')
load('//lib/presubmit.star', 'presubmit')


infra.cq_group(
    name = 'luci-py cq',
    repo = 'https://chromium.googlesource.com/infra/luci/luci-py',
)

presubmit.builder(
    name = 'Luci-py Presubmit',
    cq_group = 'luci-py cq',
    repo_name = 'luci_py',
)
