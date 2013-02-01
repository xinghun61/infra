# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import webapp2

import app
import base_page
import utils


class BuildData(object):
  """Represents a single build in the waterfall.

  Not yet used (this backend only renders a console so far).
  TODO(agable): Use, and include step-level info.
  """

  STATUS_ENUM = (
      'notstarted',
      'running',
      'success',
      'warnings',
      'failure',
      'exception',
  )

  def __init__(self):
    self.status = 0


class RowData(object):
  """Represents a single row of the console.
  
  Includes all individual builder statuses.
  """

  def __init__(self):
    self.revision = 0
    self.committer = None
    self.comment = None
    self.details = None
    self.status = {}
    self.timestamp = datetime.datetime.now()


class MergerData(object):
  """Persistent data storage class.

  Holds all of the data we have about the last 100 revisions.
  Keeps it organized and can render it upon request.
  """

  def __init__(self):
    self.SIZE = 100
    self.rows = {}
    self.latest_rev = 0
    self.ordered_builders = []
    self.failures = {}

  def bootstrap(self):
    """Fills an empty MergerData with 100 rows of data."""
    latest_rev = int(app.get_and_cache_rowdata('latest_rev')['rev_number'])
    if not latest_rev:
      logging.error("MergerData.bootstrap(): Didn't get latest_rev. Aborting.")
      return
    n = latest_rev
    num_rows_saved = num_rows_skipped = 0
    while num_rows_saved < self.SIZE and num_rows_skipped < 10:
      logging.info('MergerData.bootstrap(): Getting revision %s' % n)
      curr_row = RowData()
      for m in app.DEFAULT_MASTERS_TO_MERGE:
        # Fetch the relevant data from the datastore / cache.
        row_data = app.get_and_cache_rowdata('%s/console/%s' % (m, n))
        if not row_data:
          continue
        # Only grab the common data from the main master.
        if m == 'chromium.main':
          curr_row.revision = int(row_data['rev_number'])
          curr_row.committer = row_data['name']
          curr_row.comment = row_data['comment']
          curr_row.details = row_data['details']
        curr_row.status[m] = row_data['status']
      # If we didn't get any data, that revision doesn't exist, so skip on.
      if not curr_row.revision:
        logging.info('MergerData.bootstrap(): No data for revision %s' % n)
        num_rows_skipped += 1
        n -= 1
        continue
      logging.info('MergerData.bootstrap(): Got data for revision %s' % n)
      self.rows[n] = curr_row
      num_rows_skipped = 0
      num_rows_saved += 1
      n -= 1
    self.latest_rev = max(self.rows.keys())


class MergerUpdateAction(base_page.BasePage):
  """Handles update requests.

  Takes data gathered by the cronjob and pulls it into active memory.
  """

  def get(self):
    logging.info("***BACKEND MERGER UPDATE***")
    logging.info('BEGIN Stored rows are: %s' % sorted(data.rows))
    latest_rev = int(app.get_and_cache_rowdata('latest_rev')['rev_number'])
    logging.info('Merger.update(): latest_rev = %s' % latest_rev)
    # We may have brand new rows, so store them.
    if latest_rev not in data.rows:
      logging.info('Merger.update(): Handling new rows.')
      for n in xrange(data.latest_rev + 1, latest_rev + 1):
        logging.info('Merger.update(): Getting revision %s' % n)
        curr_row = RowData()
        for m in app.DEFAULT_MASTERS_TO_MERGE:
          # Fetch the relevant data from the datastore / cache.
          row_data = app.get_and_cache_rowdata('%s/console/%s' % (m, n))
          if not row_data:
            continue
          # Only grab the common data from the main master.
          if m == 'chromium.main':
            curr_row.revision = int(row_data['rev_number'])
            curr_row.committer = row_data['name']
            curr_row.comment = row_data['comment']
            curr_row.details = row_data['details']
          curr_row.status[m] = row_data['status']
        # If we didn't get any data, that revision doesn't exist, so skip on.
        if not curr_row.revision:
          logging.info('Merger.update(): No data for revision %s' % n)
          continue
        logging.info('Merger.update(): Got data for revision %s' % n)
        data.rows[n] = curr_row
    # Update our stored latest_rev to reflect the new data.
    data.latest_rev = max(data.rows.keys())
    # Now update the status of the rest of the rows.
    offset = 0
    logging.info('Merger.update(): Updating rows.')
    while offset < data.SIZE:
      n = data.latest_rev - offset
      logging.info('Merger.update(): Checking revision %s' % n)
      if n not in data.rows:
        logging.info('Merger.update(): Don\'t care about revision %s' % n)
        offset += 1
        continue
      curr_row = data.rows[n]
      for m in app.DEFAULT_MASTERS_TO_MERGE:
        row_data = app.get_and_cache_rowdata('%s/console/%s' % (m, n))
        if not row_data:
          continue
        curr_row.status[m] = row_data['status']
      offset += 1
      logging.info('Merger.update(): Got new data for revision %s' % n)
    # Finally delete any extra rows that we don't want to keep around.
    if len(data.rows) > data.SIZE:
      old_revs = sorted(data.rows, reverse=True)[data.SIZE:]
      logging.info('Merger.update(): Deleting rows %s' % old_revs)
      for rev in old_revs:
        del data.rows[rev]
    logging.info('FINAL Stored rows are: %s' % sorted(data.rows))
    self.response.out.write('Update completed.')


class MergerRenderAction(base_page.BasePage):

  def get(self):
    num_revs = self.request.get('numrevs')
    if num_revs:
      num_revs = utils.clean_int(num_revs, -1)
    if not num_revs or num_revs <= 0:
      num_revs = 25
    self.response.out.write('Render not yet implemented (%s rows).' % num_revs)


# Summon our persistent data model into existence.
data = MergerData()
data.bootstrap()

URLS = [
    ('/restricted/merger/update',     MergerUpdateAction),
    ('/restricted/merger/render.*',   MergerRenderAction),
]

application = webapp2.WSGIApplication(URLS, debug=True)
