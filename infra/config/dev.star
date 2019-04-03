#!/usr/bin/env lucicfg
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LUCI project configuration for the development instance of LUCI."""

load('//lib/infra.star', 'infra')


lucicfg.config(
    config_dir = 'generated',
    tracked_files = [
        'cr-buildbucket-dev.cfg',
        'luci-logdog-dev.cfg',
        'luci-scheduler-dev.cfg',
    ],
    fail_on_warnings = True,
)


luci.project(
    name = 'infra',

    buildbucket = 'cr-buildbucket-dev.appspot.com',
    logdog = 'luci-logdog-dev.appspot.com',
    scheduler = 'luci-scheduler-dev.appspot.com',
    swarming = 'chromium-swarm-dev.appspot.com',

    acls = [
        acl.entry(
            roles = [
                acl.BUILDBUCKET_READER,
                acl.LOGDOG_READER,
                acl.PROJECT_CONFIGS_READER,
                acl.SCHEDULER_READER,
            ],
            groups = 'all',
        ),
        acl.entry(
            roles = acl.SCHEDULER_OWNER,
            groups = 'project-infra-troopers',
        ),
        acl.entry(
            roles = acl.LOGDOG_WRITER,
            groups = 'luci-logdog-chromium-dev-writers',
        ),
    ],
)

luci.logdog(gs_bucket = 'chromium-luci-logdog')

luci.bucket(
    name = 'ci',
    acls = [
        acl.entry(
            roles = acl.BUILDBUCKET_TRIGGERER,
            users = 'luci-scheduler-dev@appspot.gserviceaccount.com',
        ),
    ],
)

luci.builder.defaults.swarming_tags.set(['vpython:native-python-wrapper'])
luci.builder.defaults.execution_timeout.set(30 * time.minute)


def ci_builder(
      name,
      os,
      recipe='infra_continuous',
      manual=False,
  ):
  infra.builder(
      name = name,
      bucket = 'ci',
      executable = infra.recipe(recipe),
      os = os,
      cpu = 'x86-64',
      pool = 'Chrome',  # no point in creating a dedicated pool on -dev
      service_account = 'adhoc-testing@luci-token-server-dev.iam.gserviceaccount.com',
      schedule = 'triggered' if manual else None,
      triggered_by = [] if manual else [infra.poller()],
  )


# Triggered on commits.
ci_builder(name = 'infra-continuous-trusty-64', os = 'Ubuntu-14.04')
ci_builder(name = 'infra-continuous-win-64', os = 'Windows-7-SP1')
ci_builder(name = 'infra-continuous-win10-64', os = 'Windows-10')

# Triggered manually via Scheduler UI.
ci_builder(
    name = 'goma-hello-world-trusty-64',
    os = 'Ubuntu-14.04',
    recipe = 'goma_hello_world',
    manual = True,
)
ci_builder(
    name = 'gerrit-hello-world-trusty-64',
    os = 'Ubuntu-14.04',
    recipe = 'gerrit_hello_world',
    manual = True,
)
ci_builder(
    name = 'gsutil-hello-world-trusty-64',
    os = 'Ubuntu-14.04',
    recipe = 'gsutil_hello_world',
    manual = True,
)
ci_builder(
    name = 'gsutil-hello-world-win10-64',
    os = 'Windows-10',
    recipe = 'gsutil_hello_world',
    manual = True,
)
