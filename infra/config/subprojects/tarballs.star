# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Jobs that publish tarballs with Chromium source code."""

load('//lib/infra.star', 'infra')


def builder(name, recipe, builder_dimension=None, cores=8, **kwargs):
  luci.builder(
      name = name,
      bucket = 'cron',
      executable = infra.recipe(recipe),
      service_account = 'chromium-tarball-builder@chops-service-accounts.iam.gserviceaccount.com',
      dimensions = {
          'pool': 'luci.infra.cron',
          'os': 'Ubuntu-16.04',
          'cpu': 'x86-64',
          'cores': str(cores),
          'builderless': '1',
      },
      **kwargs
  )
  luci.list_view_entry(
      builder = name,
      list_view = 'cron',
  )


builder(
    name = 'publish_tarball_dispatcher',
    recipe = 'publish_tarball',
    builder_dimension = 'publish_tarball',  # runs on same bots as 'publish_tarball'
    execution_timeout = 10 * time.minute,
    schedule = '37 */3 * * *',  # every 3 hours
    triggers = ['publish_tarball'],
)

builder(
    name = 'publish_tarball',
    recipe = 'publish_tarball',
    execution_timeout = 5 * time.hour,
    # Each trigger from 'publish_tarball_dispatcher' should result in a build.
    triggering_policy = scheduler.greedy_batching(max_batch_size=1),
    triggers = ['Build From Tarball'],
)

builder(
    name = 'Build From Tarball',
    recipe = 'build_from_tarball',
    execution_timeout = 3 * time.hour,
    # Each trigger from 'publish_tarball' should result in a build.
    triggering_policy = scheduler.greedy_batching(max_batch_size=1),
    cores=32,
)
