# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import webapp2

from model.flake import Flake, FlakeType, Issue


def _get_or_put_flake_type(step_name, test_name, last_updated):
  """Puts a FlakeType in datastore if it's not already there.

  This functions puts a FlakeType with the corresponding step_name and test_name
  into datastore if it was not already there.
  We assume the project is always 'chromium' and the config is always None.

  If the FlakeType was already in datastore, we update the last_updated field
  with the most recent of the two.

  We do this, because we want FlakeTypes to be unique, i.e. not put several
  FlakeTypes with the same step_name and test_name."""
  flake_types = FlakeType.query(FlakeType.project == 'chromium',
                                FlakeType.step_name == step_name,
                                FlakeType.test_name == test_name,
                                FlakeType.config == None).fetch(1)

  if flake_types:
    flake_type = flake_types[0]
    flake_type.last_updated = max(flake_type.last_updated, last_updated)
    return flake_type.put()

  return FlakeType(project='chromium',
                   step_name=step_name,
                   test_name=test_name,
                   config=None,
                   last_updated=last_updated).put()


def _get_flake_types_from_flake(flake):
  if flake.is_step:
    return [
        _get_or_put_flake_type(flake.name, None, flake.issue_last_updated)
    ]

  flake_type_keys = []

  for flaky_run_key in flake.occurrences:
    flaky_run = flaky_run_key.get()
    if flaky_run is not None:
      flake_type_keys.extend([
          _get_or_put_flake_type(flake_occurrence.name, flake.name,
                                 flake.issue_last_updated)
          for flake_occurrence in flaky_run.flakes
          if flake_occurrence.failure == flake.name
      ])

  return flake_type_keys


class Migrate(webapp2.RequestHandler):
  def get(self):
    if Issue.query().count(1) > 0 or FlakeType.query().count(1) > 0:
      self.response.out.write('Found Issue or FlakeType entities in datastore. '
                              'Please remove them before trying to migrate '
                              'data again.')
      self.response.set_status(400)
      return

    flakes = Flake.query(Flake.issue_id > 0).fetch()
    flake_types_by_issue = collections.defaultdict(list)
    for flake_number, flake in enumerate(flakes, 1):
      flake_types_by_issue[flake.issue_id].extend(
          _get_flake_types_from_flake(flake))
      if flake_number % 500 == 0:  # pragma: no cover
        logging.info('Processed %d flakes so far.' % flake_number)

    logging.info('Done processing FlakeTypes. Starting to process Issues')

    for issue_id, flake_type_keys in flake_types_by_issue.iteritems():
      # We might have found the same flake_type more than once.
      flake_type_keys = list(set(flake_type_keys))
      Issue(project='chromium', issue_id=issue_id,
            flake_type_keys=flake_type_keys).put()

    logging.info('Done processing Issues. Migration completed.')
