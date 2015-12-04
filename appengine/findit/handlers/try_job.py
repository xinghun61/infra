# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from base_handler import BaseHandler
from base_handler import Permission
from common import buildbucket_client


class TryJob(BaseHandler):
  """This is for testing a try-job and later the culprit finding recipe.

  No testing is added for this module as it is not for production.
  """
  PERMISSION_LEVEL = Permission.ADMIN

  def _SplitValues(self, values_str):
    values = []
    for value in values_str.split(','):
      value = value.strip()
      if value:
        values.append(value)
    return values

  def HandleGet(self):
    api = self.request.get('api', 'get')

    results = None

    if api == 'get': # Retrieve build info.
      build_ids_str = self.request.get('ids')
      build_ids = self._SplitValues(build_ids_str)
      builds = buildbucket_client.GetTryJobs(build_ids)
      results = dict(zip(build_ids, builds))
    elif api == 'put': # Trigger try-jobs.
      master_name = self.request.get('master', 'tryserver.chromium.linux')
      builder_name = self.request.get('builder', 'linux_chromium_rel_ng')
      recipe_name = self.request.get('recipe', 'chromium_trybot')

      revisions_str = self.request.get('revisions', '')
      revisions = self._SplitValues(revisions_str)

      properties_str = self.request.get('properties') or '{}'
      properties = json.loads(properties_str) or {
          # Default properties if not provided.
          'patch_storage': 'rietveld',
          'rietveld': 'https://codereview.chromium.org',
          'issue': 1393223003,
          'patchset': 1,
          'patch_project': 'chromium',
          'reason': 'testing for fun',
      }
      properties['recipe'] = recipe_name

      tags = [
          'builder:%s' % builder_name,
          'master:%s' % master_name,
      ]

      logging.info('master: %s', master_name)
      logging.info('builder: %s', builder_name)
      logging.info('recipe: %s', recipe_name)
      logging.info('revisions: %s', ','.join(revisions))
      logging.info('properties_str: %s', properties_str)
      logging.info('properties: %s', json.dumps(properties))

      try_jobs = []
      for revision in revisions:
        try_job = buildbucket_client.TryJob(
            master_name, builder_name, revision, properties, tags)
        try_jobs.append(try_job)

      builds = buildbucket_client.TriggerTryJobs(try_jobs)
      results = dict(zip(revisions, builds))

    if results is not None:
      data = {}
      for key, (error, build) in results.iteritems():
        if error:
          data[key] = {
              'reason': error.reason,
              'message': error.message,
          }
        else:
          data[key] = {
              'id': build.id,
              'status': build.status,
              'url': build.url,
          }

      return {'data': data}

    return BaseHandler.CreateError('Not implemented yet', 501)
