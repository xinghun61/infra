# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from datetime import datetime

from google.appengine.api import memcache

from appengine_module.test_results.model.testfile import TestFile

MEMCACHE_KEY = 'builder_state'


class BuilderState(object):

  @staticmethod
  def _find_master(builders, master_name):
    for master in builders['masters']:
      if master['url_name'] == master_name:
        return master
    return None

  @classmethod
  def incremental_update(cls, master_name, builder, test_type, date):
    start_time = datetime.now()
    builder_state_data = memcache.get(MEMCACHE_KEY)
    if not builder_state_data:
      logging.warning('Builder state data has not been generated.')
      return

    builders = json.loads(builder_state_data)
    master = cls._find_master(builders, master_name)
    if master is None:
      logging.warning('Incremental update for unknown master %s.', master_name)
      return

    step_data = master['tests'].get(test_type)
    if step_data is None:
      logging.warning(
          'Incremental update for unknown test_type %s in master %s.',
          test_type, master_name)
      return

    step_data['builders'][builder] = date.isoformat()

    data = json.dumps(builders, separators=(',', ':'))
    # FIXME: the cached data could have changed in the meantime, any such
    # changes would be lost here. Use memcache.cas to solve this problem.
    memcache.set(MEMCACHE_KEY, data)
    logging.debug(
        'Incrementally updating builder state took %s',
        datetime.now() - start_time)

  @staticmethod
  def _get_last_upload_date(master_name, builder, test_type):
    build_number = None
    files = TestFile.get_files(
        master_name, builder, test_type, build_number,
        'full_results.json', load_data=False, limit=1)
    if files:
      return files[0].date
    else:
      return None

  @classmethod
  def _annotate_builders_with_timestamp(cls, builders):
    start_time = datetime.now()
    for master in builders['masters']:
      master_name = master['url_name']
      for test_type, step_data in master['tests'].items():
        annotated_builders = {}
        for builder in step_data['builders']:
          last_date = cls._get_last_upload_date(master_name, builder, test_type)
          if last_date is not None:
            annotated_builders[builder] = last_date.isoformat()
          else:
            annotated_builders[builder] = None
        step_data['builders'] = annotated_builders
    logging.info('Annotating builder data %s', datetime.now() - start_time)

  @classmethod
  def refresh_all_data(cls):
    builder_data = memcache.get('buildbot_data')
    if not builder_data:
      logging.warning('Builder data has not been generated.')
      return None

    builders = json.loads(builder_data)
    cls._annotate_builders_with_timestamp(builders)

    data = json.dumps(builders, separators=(',', ':'))
    memcache.set(MEMCACHE_KEY, data)
    return data
