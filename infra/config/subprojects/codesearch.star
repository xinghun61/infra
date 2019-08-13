# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of resources for Code Search system."""

load('//lib/build.star', 'build')
load('//lib/infra.star', 'infra')


luci.bucket(
    name = 'codesearch',
    acls = [
        acl.entry(
            roles = acl.BUILDBUCKET_TRIGGERER,
            users = 'luci-scheduler@appspot.gserviceaccount.com',
        ),
    ],
)


luci.console_view(
    name = 'codesearch',
    repo = 'https://chromium.googlesource.com/chromium/src',
    include_experimental_builds = True,
)


def chromium_src_poller():
  return luci.gitiles_poller(
      name = 'codesearch-src-trigger',
      bucket = 'codesearch',
      repo = 'https://chromium.googlesource.com/chromium/src',
  )


def builder(
      name,
      executable,

      # Builder props.
      os=None,
      properties=None,
      caches=None,
      execution_timeout=None,

      # Console presentation.
      category=None,
      short_name=None,

      # Scheduler parameters.
      triggered_by=None,
      schedule=None,
  ):
  # Add mastername property so that the gen recipes can find the right
  # config in mb_config.pyl.
  properties = properties or {}
  properties['mastername'] = 'chromium.infra.codesearch'

  luci.builder(
      name = name,
      bucket = 'codesearch',
      executable = executable,
      properties = properties,
      dimensions = {
          'os': os or 'Ubuntu-16.04',
          'cpu': 'x86-64',
          'cores': '8',
          'pool': 'luci.infra.codesearch',
      },
      caches = caches,
      service_account = 'infra-codesearch@chops-service-accounts.iam.gserviceaccount.com',
      execution_timeout = execution_timeout,
      build_numbers = True,
      triggered_by = [triggered_by] if triggered_by else None,
      schedule = schedule,
  )

  luci.console_view_entry(
      builder = name,
      console_view = 'codesearch',
      category = category,
      short_name = short_name,
  )


def chromium_genfiles(short_name, name, os=None):
  builder(
      name = name,
      executable = build.recipe('chromium_codesearch'),
      os = os,
      caches = [swarming.cache(
          path = 'generated',
          name = 'codesearch_git_genfiles_repo',
      )],
      execution_timeout = 5 * time.hour,
      category = 'gen',
      short_name = short_name,
      # Gen builders are triggered by the initiator's recipe.
      triggered_by = 'codesearch-gen-chromium-initiator',
  )


def sync_submodules(
      name,
      short_name,
      source_repo,
      extra_submodules=None,
      triggered_by=None,
  ):
  properties = {'source_repo': source_repo}
  if extra_submodules:
    properties['extra_submodules'] = extra_submodules
  builder(
      name = name,
      executable = infra.recipe('sync_submodules'),
      properties = properties,
      category = 'submodules',
      short_name = short_name,
      triggered_by = triggered_by,
  )


def update_submodules_mirror(
      name,
      short_name,
      source_repo,
      target_repo,
      extra_submodules=None,
      triggered_by=None,
  ):
  properties = {
      'source_repo': source_repo,
      'target_repo': target_repo,
  }
  if extra_submodules:
    properties['extra_submodules'] = extra_submodules
  builder(
      name = name,
      execution_timeout = time.hour,
      executable = infra.recipe('update_submodules_mirror'),
      properties = properties,
      caches = [swarming.cache('codesearch_update_submodules_mirror')],
      category = 'update-submodules-mirror',
      short_name = short_name,
      triggered_by = triggered_by,
  )


# Runs every four hours (at predictable times).
builder(
    name = 'codesearch-gen-chromium-initiator',
    executable = build.recipe('chromium_codesearch_initiator'),
    category = 'gen|init',
    schedule = '0 */4 * * *',
)


chromium_genfiles('and', 'codesearch-gen-chromium-android')
chromium_genfiles('cro', 'codesearch-gen-chromium-chromiumos')
chromium_genfiles('fch', 'codesearch-gen-chromium-fuchsia')
chromium_genfiles('lnx', 'codesearch-gen-chromium-linux')
chromium_genfiles('win', 'codesearch-gen-chromium-win', os = 'Windows-10')


sync_submodules(
    name = 'codesearch-submodules-build',
    short_name = 'bld',
    source_repo = 'https://chromium.googlesource.com/chromium/tools/build',
    triggered_by = build.poller(),
)
sync_submodules(
    name = 'codesearch-submodules-infra',
    short_name = 'inf',
    source_repo = 'https://chromium.googlesource.com/infra/infra',
    triggered_by = infra.poller(),
)
sync_submodules(
    name = 'codesearch-submodules-chromium',
    short_name = 'src',
    source_repo = 'https://chromium.googlesource.com/chromium/src',
    extra_submodules = 'src/out=https://chromium.googlesource.com/chromium/src/out',
    triggered_by = chromium_src_poller(),
)


update_submodules_mirror(
    name = 'codesearch-update-submodules-mirror-src',
    short_name = 'src',
    source_repo = 'https://chromium.googlesource.com/chromium/src',
    target_repo = 'https://chromium.googlesource.com/codesearch/chromium/src',
    extra_submodules = ['src/out=https://chromium.googlesource.com/chromium/src/out'],
    triggered_by = chromium_src_poller(),
)
update_submodules_mirror(
    name = 'codesearch-update-submodules-mirror-infra',
    short_name = 'infra',
    source_repo = 'https://chromium.googlesource.com/infra/infra',
    target_repo = 'https://chromium.googlesource.com/codesearch/infra/infra',
    triggered_by = infra.poller(),
)
update_submodules_mirror(
    name = 'codesearch-update-submodules-mirror-build',
    short_name = 'build',
    source_repo = 'https://chromium.googlesource.com/chromium/tools/build',
    target_repo = 'https://chromium.googlesource.com/codesearch/chromium/tools/build',
    triggered_by = build.poller(),
)
