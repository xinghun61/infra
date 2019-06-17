# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of CrOS DUT flashing builders."""

load('//lib/infra.star', 'infra')


# Coordinates and triggers nightly ChromeOS DUT flashes for the pool of Kevin
# devices.
luci.builder(
    name = 'cros-flash-scheduler-kevin',
    bucket = 'cron',
    executable = infra.recipe('cros_flash_scheduler'),
    service_account = 'cros-flash@chops-service-accounts.iam.gserviceaccount.com',
    dimensions = {
        'os': 'Ubuntu-14.04',
        'cpu': 'x86-64',
        'cores': '2',
        'pool': 'luci.infra.cron',
        'builderless': '1',
    },
    properties = {
        'device_type': 'kevin',
        'swarming_pool': 'chrome-cros-dut',
        'swarming_server': 'chromium-swarm.appspot.com',
    },
    execution_timeout = 3 * time.hour,
    triggered_by = [
        luci.gitiles_poller(
            name = 'cros-flash-scheduler-kevin-trigger',
            bucket = 'cron',
            repo = 'https://chromium.googlesource.com/chromium/src',
            path_regexps = ['chromeos/CHROMEOS_LKGM'],
        ),
    ],
)
luci.list_view_entry(
    builder = 'cros-flash-scheduler-kevin',
    list_view = 'cron',
)


# The builder which runs the cros_flash recipe. All CrOS DUT swarming bots
# belong to this builder. Each build flashes its bot's DUT to an image specified
# by recipe properties. Note that these machines mainly run chromium tests and
# consequently belong to pool:Chrome. Since the flashing task is written as a
# recipe and triggered via buildbucket, this builder must exist to pick up the
# build requests.
luci.builder(
    name = 'cros-dut-flash',
    bucket = 'cron',
    # This recipe flashes the bot's CrOS DUT to a version specified via recipe
    # properties. This runs as a recipe because the flashing makes use of local
    # checkouts and caches. Consequently, this builder exists to trigger the
    # recipes via buildbucket.
    executable = infra.recipe('cros_flash'),
    dimensions = {
        'os': 'ChromeOS',
        'pool': 'chrome-cros-dut',
    },
    execution_timeout = 2 * time.hour,
)
