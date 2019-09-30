# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of luci-py.git CI resources."""

load('//lib/build.star', 'build')
load('//lib/infra.star', 'infra')

cq_group = 'luci-py cq'

infra.cq_group(
    name = cq_group,
    repo = 'https://chromium.googlesource.com/infra/luci/luci-py',
)


def try_builder(
      name,
      os,
      experiment_percentage=None,
      properties=None
  ):
  infra.builder(
      name = name,
      bucket = 'try',
      executable = infra.recipe('luci_py'),
      os = os,
      properties = properties,
  )
  luci.cq_tryjob_verifier(
      builder = name,
      cq_group = cq_group,
      experiment_percentage = experiment_percentage,
      disable_reuse = (properties or {}).get('presubmit'),
  )


build.presubmit(
    name = 'luci-py-try-presubmit',
    cq_group = cq_group,
    repo_name = 'luci_py',
    os = 'Ubuntu-16.04',
    # The default 8-minute timeout is a problem for luci-py.
    # See https://crbug.com/917479 for context.
    timeout_s = 900,
    vpython_spec_path = '.vpython',
)

try_builder(
    name = 'luci-py-try-xenial-64',
    os = 'Ubuntu-16.04',
    properties = {'presubmit': True},
)
