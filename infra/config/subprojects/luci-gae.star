# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of luci/gae.git CI resources."""

load('//lib/infra.star', 'infra')


REPO_URL = 'https://chromium.googlesource.com/infra/luci/gae'


infra.console_view(
    name = 'luci-gae',
    title = 'luci-gae repository console',
    repo = REPO_URL,
)
infra.cq_group(name = 'luci-gae cq', repo = REPO_URL)


def ci_builder(name, os):
  infra.builder(
      name = name,
      bucket = 'ci',
      executable = infra.recipe('luci_gae'),
      os = os,
      triggered_by = [
          luci.gitiles_poller(
              name = 'luci-gae-gitiles-trigger',
              bucket = 'ci',
              repo = REPO_URL,
          ),
      ],
      gatekeeper_group = 'chromium.infra',
  )
  luci.console_view_entry(
      builder = name,
      console_view = 'luci-gae',
      category = infra.category_from_os(os, short=True),
  )


def try_builder(name, os, presubmit=False):
  infra.builder(
      name = name,
      bucket = 'try',
      executable = infra.recipe('luci_gae'),
      os = os,
  )
  luci.cq_tryjob_verifier(
      builder = name,
      cq_group = 'luci-gae cq',
      disable_reuse = presubmit,
  )


ci_builder(name = 'luci-gae-continuous-trusty-64', os = 'Ubuntu-14.04')
ci_builder(name = 'luci-gae-continuous-mac', os = 'Mac-10.13')
ci_builder(name = 'luci-gae-continuous-win', os = 'Windows-10')

try_builder(name = 'luci-gae-try-linux-trusty-64', os = 'Ubuntu-14.04')
try_builder(name = 'luci-gae-try-linux-xenial-64', os = 'Ubuntu-16.04')
try_builder(name = 'luci-gae-try-presubmit', os = 'Ubuntu-16.04', presubmit = True)
