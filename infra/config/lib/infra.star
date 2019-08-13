# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions and constants related to infra.git used by all modules."""


def poller():
  """Defines a gitiles poller polling infra.git repo."""
  return luci.gitiles_poller(
      name = 'infra-gitiles-trigger',
      bucket = 'ci',
      repo = infra.REPO_URL,
  )


def recipe(name):
  """Defines a recipe hosted in the infra.git recipe bundle."""
  return luci.recipe(
      name = name,
      cipd_package = 'infra/recipe_bundles/chromium.googlesource.com/infra/infra',
  )


def console_view(name, title, repo=None):
  """Defines a console view with infra header."""
  luci.console_view(
      name = name,
      title = title,
      repo = repo or infra.REPO_URL,
      header = '//data/infra_console_header.textpb',
  )


def cq_group(name, repo=None, tree_status_host=None):
  """Defines a CQ group watching refs/heads/*."""
  luci.cq_group(
      name = name,
      watch = cq.refset(
          repo = repo or infra.REPO_URL,
          refs = ['refs/heads/master'],
      ),
      tree_status_host = tree_status_host,
      retry_config = cq.RETRY_NONE,
      cancel_stale_tryjobs = True,
  )


def builder(
      *,

      # Basic required stuff.
      name,
      bucket,
      executable,

      # Dimensions.
      os,
      cpu=None,
      pool=None,

      # Swarming environ.
      service_account=None,

      # Misc tweaks.
      properties=None,
      gatekeeper_group=None,
      schedule=None,

      # Triggering relations.
      triggered_by=None
  ):
  """Defines a basic infra builder (CI or Try).

  It is a builder that needs an infra.git checkout to do stuff.

  Depending on value of `bucket`, will chose a default pool (ci or flex try),
  the service account and build_numbers settings.
  """
  if bucket == 'ci':
    pool = pool or 'luci.flex.ci'
    service_account = service_account or infra.SERVICE_ACCOUNT_CI
    build_numbers = True
  elif bucket == 'try':
    pool = pool or 'luci.flex.try'
    service_account = service_account or infra.SERVICE_ACCOUNT_TRY
    build_numbers = None  # leave it unset in the generated file
  else:
    fail('unknown bucket')

  caches = [infra.cache_gclient_with_go]
  if os.startswith('Mac'):
    caches.append(infra.cache_osx_sdk)

  if gatekeeper_group:
    properties = properties or {}
    properties['$gatekeeper'] = {'group': gatekeeper_group}

  luci.builder(
      name = name,
      bucket = bucket,
      executable = executable,
      dimensions = {'os': os, 'cpu': cpu or 'x86-64', 'pool': pool},
      service_account = service_account,
      properties = properties,
      caches = caches,
      build_numbers = build_numbers,
      schedule = schedule,
      task_template_canary_percentage = 30,
      triggered_by = triggered_by,
  )


_OS_TO_CATEGORY = {
    'Ubuntu': 'linux',
    'Mac': 'mac',
    'Windows': 'win',
}


def category_from_os(os, short=False):
  """Given e.g. 'Ubuntu-16.10' returns e.g. 'linux|16.10'."""
  # Win7 seems to be special.
  if os == 'Windows':
    return 'win' if short else 'win|7'
  os, _, ver = os.partition('-')
  category = _OS_TO_CATEGORY.get(os, os.lower())
  if not short:
    category += '|' + ver
  return category


infra = struct(
    REPO_URL = 'https://chromium.googlesource.com/infra/infra',

    # Note: try account is also used by all presubmit builders in this project.
    SERVICE_ACCOUNT_TRY = 'infra-try-builder@chops-service-accounts.iam.gserviceaccount.com',
    SERVICE_ACCOUNT_CI = 'infra-ci-builder@chops-service-accounts.iam.gserviceaccount.com',

    cache_gclient_with_go = swarming.cache('infra_gclient_with_go'),
    cache_osx_sdk = swarming.cache('osx_sdk'),

    poller = poller,
    recipe = recipe,
    console_view = console_view,
    cq_group = cq_group,
    builder = builder,

    category_from_os = category_from_os,
)
