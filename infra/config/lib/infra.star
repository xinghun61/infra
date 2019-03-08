# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions and constants related to infra.git used by all modules."""


def poller(name, repo=None):
  """Defines a gitiles poller."""
  luci.gitiles_poller(
      name = name,
      bucket = 'ci',
      repo = repo or infra.REPO_URL,
  )


def recipe(name):
  """Defines a recipe hosted in the infra.git recipe bundle."""
  luci.recipe(
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


def cq_group(name, repo=None):
  """Defines a CQ group watching refs/heads/*."""
  luci.cq_group(
      name = name,
      watch = cq.refset(
          repo = repo or infra.REPO_URL,
          refs = [r'refs/heads/.+'],
      ),
      tree_status_host = 'infra-status.appspot.com',
      retry_config = cq.RETRY_NONE,
  )


def builder(
      *,

      # Basic required stuff.
      name,
      bucket,
      recipe,

      # Dimensions (all required).
      os,
      cpu,
      pool,

      # Swarming environ.
      service_account=None,

      # Misc tweaks.
      properties=None,
      build_numbers=None,
      schedule=None,

      # Triggering relations.
      triggered_by=None
  ):
  """Defines a basic infra builder (CI or Try).

  It is a builder that needs an infra.git checkout to do stuff.
  """
  caches = [infra.cache_gclient_with_go]
  if os.startswith('Mac'):
    caches.append(infra.cache_osx_sdk)
  luci.builder(
      name = name,
      bucket = bucket,
      recipe = recipe,
      dimensions = {'os': os, 'cpu': cpu, 'pool': pool},
      execution_timeout = 30 * time.minute,
      swarming_tags = ['vpython:native-python-wrapper'],
      service_account = service_account,
      properties = properties,
      caches = caches,
      build_numbers = build_numbers,
      schedule = schedule,
      triggered_by = triggered_by,
  )


_OS_TO_CATEGORY = {
    'Ubuntu': 'linux',
    'Mac': 'mac',
    'Windows': 'win',
}


def category_from_os(os):
  """Given e.g. 'Ubuntu-16.10' returns e.g. 'linux|16.10'."""
  # Win7 seems to be special.
  if os == 'Windows':
    return 'win|7'
  os, _, ver = os.partition('-')
  return _OS_TO_CATEGORY.get(os, os.lower()) + '|' + ver


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
