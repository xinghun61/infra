#!/usr/bin/env lucicfg
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LUCI project configuration for the production instance of LUCI.

After modifying this file execute it ('./main.star') to regenerate the configs.
This is also enforced by PRESUBMIT.py script.

Includes CI configs for the following subprojects:
  * Codesearch.
  * Gatekeeper cron.
  * Gsubtreed crons.
  * WPT autoroller crons.
  * Chromium tarball publisher.
  * Chromium LKGR finder cron.
  * CrOS DUT flashing cron job.
  * https://chromium.googlesource.com/chromium/tools/build
  * https://chromium.googlesource.com/chromium/tools/depot_tools
  * https://chromium.googlesource.com/infra/infra
  * https://chromium.googlesource.com/infra/luci/gae
  * https://chromium.googlesource.com/infra/luci/luci-go
  * https://chromium.googlesource.com/infra/luci/luci-py
  * https://chromium.googlesource.com/infra/luci/recipes-py
  * https://chromium.googlesource.com/infra/testing/expect_tests
"""

lucicfg.check_version('1.7.8', 'Please update depot_tools')


# Tell lucicfg what files it is allowed to touch.
lucicfg.config(
    config_dir = 'generated',
    tracked_files = [
        'commit-queue.cfg',
        'cr-buildbucket.cfg',
        'luci-logdog.cfg',
        'luci-milo.cfg',
        'luci-scheduler.cfg',
        'project.cfg',
    ],
    fail_on_warnings = True,
)


luci.project(
    name = 'infra',

    buildbucket = 'cr-buildbucket.appspot.com',
    logdog = 'luci-logdog.appspot.com',
    milo = 'luci-milo.appspot.com',
    scheduler = 'luci-scheduler.appspot.com',
    swarming = 'chromium-swarm.appspot.com',

    acls = [
        # Publicly readable.
        acl.entry(
            roles = [
                acl.BUILDBUCKET_READER,
                acl.LOGDOG_READER,
                acl.PROJECT_CONFIGS_READER,
                acl.SCHEDULER_READER,
            ],
            groups = 'all',
        ),
        # Allow committers to use CQ and to force-trigger and stop CI builds.
        acl.entry(
            roles = [
                acl.SCHEDULER_OWNER,
                acl.CQ_COMMITTER,
            ],
            groups = 'project-infra-committers',
        ),
        # Ability to launch CQ dry runs.
        acl.entry(
            roles = acl.CQ_DRY_RUNNER,
            groups = 'project-infra-tryjob-access',
        ),
        # Group with bots that have write access to the Logdog prefix.
        acl.entry(
            roles = acl.LOGDOG_WRITER,
            groups = 'luci-logdog-chromium-writers',
        ),
    ],
)


# Per-service tweaks.
luci.logdog(gs_bucket = 'chromium-luci-logdog')
luci.milo(
    logo = 'https://storage.googleapis.com/chrome-infra-public/logo/chrome-infra-logo-200x200.png',
    favicon = 'https://storage.googleapis.com/chrome-infra-public/logo/favicon.ico',
)
luci.cq(status_host = 'chromium-cq-status.appspot.com')


# Global builder defaults.
luci.builder.defaults.execution_timeout.set(30 * time.minute)
luci.builder.defaults.properties.set({'$kitchen': {'emulate_gce' : True}})


# Resources shared by all subprojects.


luci.bucket(name = 'ci')

luci.bucket(
    name = 'try',
    acls = [
        acl.entry(
            roles = acl.BUILDBUCKET_TRIGGERER,
            groups = [
                'project-infra-tryjob-access',
                'service-account-cq',
            ],
        ),
    ],
)

luci.bucket(
    name = 'cron',
    acls = [
        acl.entry(
            roles = acl.BUILDBUCKET_TRIGGERER,
            users = [
                # Allow the cros-flash-scheduler to schedule other builders in
                # the bucket, see //subprojects/cros_flash.star.
                'cros-flash@chops-service-accounts.iam.gserviceaccount.com',
            ],
        ),
    ],
)

luci.list_view(name = 'cron')

# Per-subproject resources. They may refer to the shared resources defined
# above by name.

exec('//subprojects/build.star')
exec('//subprojects/codesearch.star')
exec('//subprojects/cros_flash.star')
exec('//subprojects/depot_tools.star')
exec('//subprojects/expect_tests.star')
exec('//subprojects/gatekeeper.star')
exec('//subprojects/gsubtreed.star')
exec('//subprojects/infra.star')
exec('//subprojects/lkgr.star')
exec('//subprojects/luci-gae.star')
exec('//subprojects/luci-go.star')
exec('//subprojects/luci-py.star')
exec('//subprojects/recipe_engine.star')
exec('//subprojects/tarballs.star')
exec('//subprojects/wpt.star')
