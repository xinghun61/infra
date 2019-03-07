# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions and constants related to infra.git used by all modules."""


def poller(name):
  """Defines a gitiles poller of infra.git repo."""
  luci.gitiles_poller(
      name = name,
      bucket = 'ci',
      repo = infra.REPO_URL,
  )


def recipe(name):
  """Defines a recipe hosted in the infra.git recipe bundle."""
  luci.recipe(
      name = name,
      cipd_package = 'infra/recipe_bundles/chromium.googlesource.com/infra/infra',
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
      caches = caches,
      build_numbers = build_numbers,
      schedule = schedule,
      triggered_by = triggered_by,
  )


def category_from_os(os):
  """Given e.g. 'Ubuntu-16.10' returns e.g. 'linux'."""
  if os.startswith('Ubuntu'):
    return 'linux'
  if os.startswith('Mac'):
    return 'mac'
  if os.startswith('Win'):
    return 'win'
  return os.lower()


infra = struct(
    REPO_URL = 'https://chromium.googlesource.com/infra/infra',

    cache_gclient_with_go = swarming.cache('infra_gclient_with_go'),
    cache_osx_sdk = swarming.cache('osx_sdk'),

    poller = poller,
    recipe = recipe,
    builder = builder,

    category_from_os = category_from_os,
)
