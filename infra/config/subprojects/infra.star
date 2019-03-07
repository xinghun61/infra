# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of infra.git CI resources."""

load('//lib/infra.star', 'infra')


infra.recipe(name = 'infra_continuous')
infra.recipe(name = 'infra_repo_trybot')
infra.recipe(name = 'infra_wct_tester')


luci.console_view(
    name = 'infra',
    repo = infra.REPO_URL,
    title = 'infra/infra repository console',
    header = '//data/infra_console_header.textpb',
)


luci.cq_group(
    name = 'infra cq',
    watch = cq.refset(repo = infra.REPO_URL, refs = [r'refs/heads/.+']),
    tree_status_host = 'infra-status.appspot.com',
    retry_config = cq.RETRY_NONE,
)


def ci_builder(name, os, cpu='x86-64'):
  infra.builder(
      name = name,
      bucket = 'ci',
      recipe = 'infra_continuous',
      os = os,
      cpu = cpu,
      pool = 'luci.flex.ci',
      service_account = 'infra-ci-builder@chops-service-accounts.iam.gserviceaccount.com',
      build_numbers = True,
      triggered_by = ['infra-gitiles-trigger'],
  )
  luci.console_view_entry(
      builder = name,
      console_view = 'infra',
      category = infra.category_from_os(os),
  )


def try_builder(name, os, recipe=None):
  infra.builder(
      name = name,
      bucket = 'try',
      recipe = recipe or 'infra_repo_trybot',
      os = os,
      cpu = 'x86-64',
      pool = 'luci.flex.try',
      service_account = 'infra-try-builder@chops-service-accounts.iam.gserviceaccount.com',
  )
  luci.cq_tryjob_verifier(
      builder = name,
      cq_group = 'infra cq',
  )


# CI Linux.
ci_builder(name = 'infra-continuous-zesty-64', os = 'Ubuntu-17.04')
ci_builder(name = 'infra-continuous-yakkety-64', os = 'Ubuntu-16.10')
ci_builder(name = 'infra-continuous-xenial-64', os = 'Ubuntu-16.04')
ci_builder(name = 'infra-continuous-trusty-64', os = 'Ubuntu-14.04')
ci_builder(name = 'infra-continuous-precise-64', os = 'Ubuntu-12.04')

# CI OSX.
ci_builder(name = 'infra-continuous-mac-10.13-64', os = 'Mac-10.13')
ci_builder(name = 'infra-continuous-mac-10.12-64', os = 'Mac-10.12')
ci_builder(name = 'infra-continuous-mac-10.11-64', os = 'Mac-10.11')
ci_builder(name = 'infra-continuous-mac-10.10-64', os = 'Mac-10.10')
ci_builder(name = 'infra-continuous-mac-10.9-64', os = 'Mac-10.9')

# CI Win.
ci_builder(name = 'infra-continuous-win7-64', os = 'Windows')
ci_builder(name = 'infra-continuous-win7-32', os = 'Windows', cpu = 'x86-32')
ci_builder(name = 'infra-continuous-win10-64', os = 'Windows-10')

# All trybots.
try_builder(name = 'Infra Linux Trusty 64 Tester', os = 'Ubuntu-14.04')
try_builder(name = 'Infra Mac Tester', os = 'Mac-10.13')
try_builder(name = 'Infra Win Tester', os = 'Windows')
try_builder(name = 'Infra WCT Tester', os = 'Ubuntu-14.04', recipe = 'infra_wct_tester')

# TODO(vadimsh): Add 'Infra Presubmit'.
