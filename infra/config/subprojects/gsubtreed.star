# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of gsubtreed builders."""

load('//lib/infra.star', 'infra')


def gsubtreed_cron(
      name,
      service_account,
      target_repo,
      execution_timeout=None,
      schedule=None,
  ):
  luci.builder(
      name = name,
      bucket = 'cron',
      recipe = infra.recipe('gsubtreed'),
      properties = {
          # Don't loop, run just once. For lesser used gsubtreeds, rate of
          # commit is low. This also allows for more efficient machine sharing.
          'cycle_time_sec': 1,
          'target_repo': target_repo,
      },
      dimensions = {
          # Share machines with other gsubtreed- builders.
          'builder': 'gsubtreed-shared',
          'os': 'Ubuntu-14.04',
          'cpu': 'x86-64',
          'pool': 'luci.infra.cron',
      },
      service_account = service_account,
      # 1 stuck builder shouldn't block others using the same pool of machines.
      execution_timeout = execution_timeout or 10 * time.minute,
      schedule = 'with 240s interval',
  )
  luci.list_view_entry(
      builder = name,
      list_view = 'cron',
  )


# TODO(vadimsh): All these different service accounts are not necessary as long
# as all builders run on the same pool of machines. We can have single gsubtreed
# account instead.


gsubtreed_cron(
    name = 'gsubtreed-chromium',
    service_account = 'gsubtreed-chromium-src@chops-service-accounts.iam.gserviceaccount.com',
    target_repo = 'https://chromium.googlesource.com/chromium/src',
    # Re-bootstrapping chromium repo takes 1+ hours.
    execution_timeout = 3 * time.hour,
)
gsubtreed_cron(
    name = 'gsubtreed-chromiumos-platform2',
    service_account = 'gsubtreed-chromiumos-platform2@chops-service-accounts.iam.gserviceaccount.com',
    target_repo = 'https://chromium.googlesource.com/chromiumos/platform2',
)
gsubtreed_cron(
    name = 'gsubtreed-aosp-platform-system-core',
    service_account = 'gsubtreed-aosp@chops-service-accounts.iam.gserviceaccount.com',
    target_repo = 'https://chromium.googlesource.com/aosp/platform/system/core',
)
gsubtreed_cron(
    name = 'gsubtreed-llvm-clang',
    service_account = 'gsubtreed-llvm-clang@chops-service-accounts.iam.gserviceaccount.com',
    target_repo = 'https://chromium.googlesource.com/external/github.com/llvm-mirror/clang',
)
gsubtreed_cron(
    name = 'gsubtreed-infra',
    service_account = 'gsubtreed-infra-infra@chops-service-accounts.iam.gserviceaccount.com',
    target_repo = 'https://chromium.googlesource.com/infra/infra',
)
gsubtreed_cron(
    name = 'gsubtreed-luci-py',
    service_account = 'gsubtreed-luci-py@chops-service-accounts.iam.gserviceaccount.com',
    target_repo = 'https://chromium.googlesource.com/infra/luci/luci-py',
)
