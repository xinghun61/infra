# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LKGR finder cron."""

load('//lib/infra.star', 'infra')

luci.builder(
    name = 'chromium-lkgr-finder',
    bucket = 'cron',
    executable = infra.recipe('lkgr_finder'),
    service_account = 'chromium-lkgr-finder-builder@chops-service-accounts.iam.gserviceaccount.com',
    dimensions = {
        'os': 'Ubuntu-16.04',
        'cpu': 'x86-64',
        'cores': '8',
        'pool': 'luci.infra.cron',
        'builderless': '1',
    },
    execution_timeout = 2 * time.hour,
    schedule = 'with 3000s interval',
)

luci.list_view_entry(
    list_view = 'cron',
    builder = 'chromium-lkgr-finder',
)
