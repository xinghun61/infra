# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of gsubtreed builders."""

load('//lib/infra.star', 'infra')


def gsubtreed_cron(
      name,
      target_repo,
      execution_timeout=None,
      schedule=None,
  ):
  luci.builder(
      name = name,
      bucket = 'cron',
      executable = infra.recipe('gsubtreed'),
      properties = {
          # Don't loop, run just once. For lesser used gsubtreeds, rate of
          # commit is low. This also allows for more efficient machine sharing.
          'cycle_time_sec': 1,
          'target_repo': target_repo,
      },
      dimensions = {
          'os': 'Ubuntu-16.04',
          'cpu': 'x86-64',
          'cores': '2',
          'pool': 'luci.infra.cron',
          'builderless': '1',
      },
      service_account = 'gsubtreed@chops-service-accounts.iam.gserviceaccount.com',
      # 1 stuck builder shouldn't block others using the same pool of machines.
      execution_timeout = execution_timeout or 10 * time.minute,
      schedule = schedule or 'with 240s interval',
  )
  luci.list_view_entry(
      builder = name,
      list_view = 'cron',
  )


gsubtreed_cron(
    name = 'gsubtreed-chromium',
    target_repo = 'https://chromium.googlesource.com/chromium/src',
    # Re-bootstrapping chromium repo takes 1+ hours.
    execution_timeout = 3 * time.hour,
    # We want to have minimal delay.
    schedule = 'continuously',
)
gsubtreed_cron(
    name = 'gsubtreed-chromiumos-platform2',
    target_repo = 'https://chromium.googlesource.com/chromiumos/platform2',
)
gsubtreed_cron(
    name = 'gsubtreed-aosp-platform-system-core',
    target_repo = 'https://chromium.googlesource.com/aosp/platform/system/core',
)
gsubtreed_cron(
    name = 'gsubtreed-llvm-clang',
    target_repo = 'https://chromium.googlesource.com/external/github.com/llvm-mirror/clang',
)
gsubtreed_cron(
    name = 'gsubtreed-selenium',
    target_repo = 'https://chromium.googlesource.com/external/github.com/SeleniumHQ/selenium',
)
gsubtreed_cron(
    name = 'gsubtreed-infra',
    target_repo = 'https://chromium.googlesource.com/infra/infra',
)
gsubtreed_cron(
    name = 'gsubtreed-luci-py',
    target_repo = 'https://chromium.googlesource.com/infra/luci/luci-py',
)
