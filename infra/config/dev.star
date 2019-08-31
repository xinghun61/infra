#!/usr/bin/env lucicfg
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LUCI project configuration for the development instance of LUCI.

After modifying this file execute it ('./dev.star') to regenerate the configs.
This is also enforced by PRESUBMIT.py script.
"""

load('//lib/build.star', 'build')
load('//lib/infra.star', 'infra')


lucicfg.config(
    config_dir = 'generated',
    tracked_files = [
        'cr-buildbucket-dev.cfg',
        'luci-logdog-dev.cfg',
        'luci-notify-dev.cfg',
        'luci-notify-dev/email-templates/*',
        'luci-scheduler-dev.cfg',
        'tricium-dev.cfg',
    ],
    fail_on_warnings = True,
)


# Just copy tricium-dev.cfg as is to the outputs.
lucicfg.emit(
    dest = 'tricium-dev.cfg',
    data = io.read_file('tricium-dev.cfg'),
)


luci.project(
    name = 'infra',

    buildbucket = 'cr-buildbucket-dev.appspot.com',
    logdog = 'luci-logdog-dev.appspot.com',
    notify = 'luci-notify-dev.appspot.com',
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

luci.bucket(name = 'ci')

luci.builder.defaults.execution_timeout.set(30 * time.minute)
luci.builder.defaults.properties.set({'$kitchen': {'emulate_gce' : True}})


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


ci_builder(name = 'infra-continuous-xenial-64', os = 'Ubuntu-16.04')
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
    name = 'goma-hello-world-xenial-64',
    os = 'Ubuntu-16.04',
    executable = infra.recipe('goma_hello_world'),
    schedule = 'with 10m interval',
)
adhoc_builder(
    name = 'gerrit-hello-world-xenial-64',
    os = 'Ubuntu-16.04',
    executable = infra.recipe('gerrit_hello_world'),
    schedule = 'triggered',  # triggered manually via Scheduler UI
)
adhoc_builder(
    name = 'gsutil-hello-world-xenial-64',
    os = 'Ubuntu-16.04',
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
adhoc_builder(
    name = 'build-proto-experiment-linux',
    os = 'Ubuntu',
    executable = luci.recipe(
      name = 'futures:examples/background_helper',
      cipd_package = 'infra/recipe_bundles/chromium.googlesource.com/infra/luci/recipes-py'
    ),
    schedule = 'with 10m interval',
)
adhoc_builder(
    name = 'build-proto-experiment-win',
    os = 'Windows-10',
    executable = luci.recipe(
      name = 'futures:examples/background_helper',
      cipd_package = 'infra/recipe_bundles/chromium.googlesource.com/infra/luci/recipes-py'
    ),
    schedule = 'with 10m interval',
)


luci.notifier(
    name = 'nodir-spam',
    on_success = True,
    on_failure = True,
    notify_emails = ['nodir+spam@google.com'],
    template = 'test',
    notified_by = ['infra-continuous-xenial-64']
)

luci.notifier_template(
    name = 'test',
    body = """{{.Build.Builder.IDString}} notification

<a href="{{.Build.ViewUrl}}">Build {{.Build.Number}}</a>
has completed.

{{template "steps" .}}
"""
)

luci.notifier_template(
    name = 'steps',
    body = """Renders steps.

<ol>
{{range $s := .Steps}}
  <li>{{$s.Name}}</li>
{{end}}
</ol>
"""
)
