#!/usr/bin/env lucicfg
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LUCI project configuration for the development instance of LUCI."""

load('//lib/build.star', 'build')
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
  ):
  infra.builder(
      name = name,
      bucket = 'ci',
      executable = infra.recipe(recipe),
      os = os,
      cpu = 'x86-64',
      pool = 'Chrome',  # no point in creating a dedicated pool on -dev
      service_account = 'adhoc-testing@luci-token-server-dev.iam.gserviceaccount.com',
      triggered_by = [infra.poller()],
  )


ci_builder(name = 'infra-continuous-trusty-64', os = 'Ubuntu-14.04')
ci_builder(name = 'infra-continuous-win-64', os = 'Windows-7-SP1')
ci_builder(name = 'infra-continuous-win10-64', os = 'Windows-10')


def adhoc_builder(
      name,
      os,
      executable,
      extra_dims=None,
      properties=None,
      schedule=None,
      triggered_by=None,
  ):
  dims = {'os': os, 'cpu': 'x86-64', 'pool': 'Chrome'}
  if extra_dims:
    dims.update(**extra_dims)
  luci.builder(
      name = name,
      bucket = 'ci',
      executable = executable,
      dimensions = dims,
      properties = properties,
      service_account = 'adhoc-testing@luci-token-server-dev.iam.gserviceaccount.com',
      build_numbers = True,
      schedule = schedule,
      triggered_by = triggered_by,
  )


adhoc_builder(
    name = 'goma-hello-world-trusty-64',
    os = 'Ubuntu-14.04',
    executable = infra.recipe('goma_hello_world'),
    schedule = 'with 10m interval',
)
adhoc_builder(
    name = 'gerrit-hello-world-trusty-64',
    os = 'Ubuntu-14.04',
    executable = infra.recipe('gerrit_hello_world'),
    schedule = 'triggered',  # triggered manually via Scheduler UI
)
adhoc_builder(
    name = 'gsutil-hello-world-trusty-64',
    os = 'Ubuntu-14.04',
    executable = infra.recipe('gsutil_hello_world'),
    schedule = 'triggered',  # triggered manually via Scheduler UI
)
adhoc_builder(
    name = 'gsutil-hello-world-win10-64',
    os = 'Windows-10',
    executable = infra.recipe('gsutil_hello_world'),
    schedule = 'triggered',  # triggered manually via Scheduler UI
)
adhoc_builder(
    name = 'infra-continuous-pack-apps',
    os = 'Ubuntu',
    executable = build.recipe('run_docker'),
    extra_dims = {'docker_installed': 'true'},
    properties = {
        'cmd_args': ['apack', 'pack', 'source/infra/appengine/cr-buildbucket/default.apack'],
        'image': 'infra_dev_env',
        'inherit_luci_context': True,
    },
    triggered_by = [infra.poller()],
)
