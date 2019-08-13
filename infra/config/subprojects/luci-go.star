# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of luci-go.git CI resources."""

load('//lib/infra.star', 'infra')


REPO_URL = 'https://chromium.googlesource.com/infra/luci/luci-go'


infra.console_view(
    name = 'luci-go',
    title = 'luci-go repository console',
    repo = REPO_URL,
)
infra.cq_group(name = 'luci-go cq', repo = REPO_URL)


def ci_builder(name, os):
  infra.builder(
      name = name,
      bucket = 'ci',
      executable = infra.recipe('luci_go'),
      os = os,
      triggered_by = [
          luci.gitiles_poller(
              name = 'luci-go-gitiles-trigger',
              bucket = 'ci',
              repo = REPO_URL,
          ),
      ],
      gatekeeper_group = 'chromium.infra',
  )
  luci.console_view_entry(
      builder = name,
      console_view = 'luci-go',
      category = infra.category_from_os(os),
  )


def try_builder(name, os, presubmit=False):
  infra.builder(
      name = name,
      bucket = 'try',
      executable = infra.recipe('luci_go'),
      os = os,
      properties = {'presubmit': True} if presubmit else None,
  )
  luci.cq_tryjob_verifier(
      builder = name,
      cq_group = 'luci-go cq',
      disable_reuse = presubmit,
  )


ci_builder(name = 'luci-go-continuous-xenial-64', os = 'Ubuntu-16.04')
ci_builder(name = 'luci-go-continuous-trusty-64', os = 'Ubuntu-14.04')
ci_builder(name = 'luci-go-continuous-mac-10.13-64', os = 'Mac-10.13')
ci_builder(name = 'luci-go-continuous-win7-64', os = 'Windows')
ci_builder(name = 'luci-go-continuous-win10-64', os = 'Windows-10')

try_builder(name = 'luci-go-try-trusty-64', os = 'Ubuntu-14.04')
try_builder(name = 'luci-go-try-xenial-64', os = 'Ubuntu-16.04')
try_builder(name = 'luci-go-try-mac', os = 'Mac-10.13')
try_builder(name = 'luci-go-try-win', os = 'Windows')
try_builder(name = 'luci-go-try-presubmit', os = 'Ubuntu-16.04', presubmit = True)
