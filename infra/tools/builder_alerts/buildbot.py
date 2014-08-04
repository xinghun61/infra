# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import logging
import operator
import os
import urlparse
import datetime

import requests

from infra.tools.builder_alerts import string_helpers

# Python logging is stupidly verbose to configure.
def setup_logging():
  logger = logging.getLogger(__name__)
  logger.setLevel(logging.DEBUG)
  handler = logging.StreamHandler()
  handler.setLevel(logging.DEBUG)
  formatter = logging.Formatter('%(levelname)s: %(message)s')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  return logger, handler


log, logging_handler = setup_logging()


CBE_BASE = 'https://chrome-build-extract.appspot.com'

# Unclear if this should be specific to builds.
class BuildCache(object):
  def __init__(self, root_path):
    self.root_path = root_path

  # Could be in operator.
  def has(self, key):
    path = os.path.join(self.root_path, key)
    return os.path.exists(path)

  def key_age(self, key):
    path = os.path.join(self.root_path, key)
    return datetime.datetime.fromtimestamp(os.path.getmtime(path))

  # Could be attr getter.
  def get(self, key):
    path = os.path.join(self.root_path, key)
    if not self.has(path):
      return None
    with open(path) as cached:
      return json.load(cached)

  # Could be attr setter.
  def set(self, key, json_object):
    path = os.path.join(self.root_path, key)
    cache_dir = os.path.dirname(path)
    if not os.path.exists(cache_dir):
      os.makedirs(cache_dir)
    with open(path, 'w') as cached:
      cached.write(json.dumps(json_object))


def master_name_from_url(master_url):
  return urlparse.urlparse(master_url).path.split('/')[-1]


def build_url(master_url, builder_name, build_number):
  quoted_name = urllib.pathname2url(builder_name)
  args = (master_url, quoted_name, build_number)
  return "%s/builders/%s/builds/%s" % args


def cache_key_for_build(master_url, builder_name, build_number):
  master_name = master_name_from_url(master_url)
  return os.path.join(master_name, builder_name, "%s.json" % build_number)


def fetch_master_json(master_url):
  master_name = master_name_from_url(master_url)
  url = '%s/get_master/%s' % (CBE_BASE, master_name)
  return requests.get(url).json()


def prefill_builds_cache(cache, master_url, builder_name):
  master_name = master_name_from_url(master_url)
  builds_url = '%s/get_builds' % CBE_BASE
  params = { 'master': master_name, 'builder': builder_name }
  response = requests.get(builds_url, params=params)
  builds = response.json()['builds']
  for build in builds:
    if not build.get('number'):
      index = builds.index(build)
      log.error('build at index %s in %s missing number?' % (index,
          response.url))
      continue
    build_number = build['number']
    key = cache_key_for_build(master_url, builder_name, build_number)
    cache.set(key, build)
  build_numbers = map(operator.itemgetter('number'), builds)
  log.debug('Prefilled (%.1fs) %s for %s %s' %
      (response.elapsed.total_seconds(),
      string_helpers.re_range(build_numbers),
      master_name, builder_name))
  return build_numbers


def fetch_and_cache_build(cache, url, cache_key):
  response = requests.get(url)
  if response.status_code != 200:
    log.error('Failed (%.1fs, %s) %s' % (response.elapsed.total_seconds(),
        response.status_code, response.url))
    return None

  try:
    build = response.json()
  except ValueError, e:
    log.error('Not caching invalid json: %s (%s): %s\n%s' % (url,
        response.status_code, e, response.text))
    return None

  log.debug('Fetched (%.1fs) %s' % (response.elapsed.total_seconds(), url))
  cache.set(cache_key, build)
  return build


def fetch_build_json(cache, master_url, builder_name, build_number):
  cache_key = cache_key_for_build(master_url, builder_name, build_number)
  build = cache.get(cache_key)
  master_name = master_name_from_url(master_url)

  # We will cache in-progress builds, but only for 2 minutes.
  if build and build.get('eta'):
    cache_age = datetime.datetime.now() - cache.key_age(cache_key)
    # Round for display.
    cache_age = datetime.timedelta(seconds=round(cache_age.total_seconds()))
    if cache_age.total_seconds() < 120:
      return build
    log.debug('Expired (%s) %s %s %s' % (cache_age,
        master_name, builder_name, build_number))
    build = None

  if not build:
    cbe_url = ('https://chrome-build-extract.appspot.com/p/%s/builders/'
        '%s/builds/%s?json=1') % (master_name, builder_name, build_number)
    build = fetch_and_cache_build(cache, cbe_url, cache_key)

  if not build:
    buildbot_url = ('https://build.chromium.org/p/%s/json/builders/'
        '%s/builds/%s') % (master_name, builder_name, build_number)
    build = fetch_and_cache_build(cache, buildbot_url, cache_key)

  return build


# This effectively extracts the 'configuration' of the build
# we could extend this beyond repo versions in the future.
def revisions_from_build(build_json):
  def _property_value(build_json, property_name):
    for prop_tuple in build_json['properties']:
      if prop_tuple[0] == property_name:
        return prop_tuple[1]

  REVISION_VARIABLES = [
    ('chromium', 'got_revision'),
    ('blink', 'got_webkit_revision'),
    ('v8', 'got_v8_revision'),
    ('nacl', 'got_nacl_revision'),
    # Skia, for whatever reason, isn't exposed in the buildbot properties so
    # don't bother to include it here.
  ]

  revisions = {}
  for repo_name, buildbot_property in REVISION_VARIABLES:
    # This is epicly stupid:  'tester' builders have the wrong
    # revision for 'got_foo_revision' and we have to use
    # parent_got_foo_revision instead, but non-tester builders
    # don't have the parent_ versions, so we have to fall back
    # to got_foo_revision in those cases!
    # Don't even think about using 'revision' that's wrong too.
    revision = _property_value(build_json, 'parent_' + buildbot_property)
    if not revision:
      revision = _property_value(build_json, buildbot_property)
    revisions[repo_name] = revision
  return revisions


def latest_revisions_for_master(cache, master_url, master_json):
  latest_revisions = collections.defaultdict(dict)
  master_name = master_name_from_url(master_url)
  for builder_name, builder_json in master_json['builders'].items():
    # recent_builds can include current builds
    recent_builds = set(builder_json['cachedBuilds'])
    active_builds = set(builder_json['currentBuilds'])
    last_finished_id = sorted(recent_builds - active_builds, reverse=True)[0]
    last_build = fetch_build_json(cache,
        master_url, builder_name, last_finished_id)
    latest_revisions[master_name][builder_name] = \
        revisions_from_build(last_build)
  return latest_revisions


def warm_build_cache(cache, master_url, builder_name,
    recent_build_ids, active_builds):
  # Cache active (in-progress) builds:
  match_builder_name = lambda build: build['builderName'] == builder_name
  actives = filter(match_builder_name, active_builds)
  for build in actives:
    key = cache_key_for_build(master_url, builder_name, build['number'])
    cache.set(key, build)

  active_build_ids = [b['number'] for b in active_builds]
  # recent_build_ids includes active ones.
  finished_build_ids = [b for b in recent_build_ids
      if b not in active_build_ids]
  last_build_id = max(finished_build_ids)
  cache_key = cache_key_for_build(master_url, builder_name, last_build_id)

  # We cache in-progress builds, so if the first finished build has a non-None
  # eta, then it's just the cached version from when it was in progress.
  cached_build = cache.get(cache_key)
  if not cached_build or cached_build.get('eta') is not None:
    # reason = 'in progress' if cached_build else 'missing'
    # log.debug('prefill reason: %s %s' % (max(finished_build_ids), reason))
    prefill_builds_cache(cache, master_url, builder_name)
