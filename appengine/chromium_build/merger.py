# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import jinja2
import webapp2

import app
import base_page
import utils

from third_party.BeautifulSoup.BeautifulSoup import BeautifulSoup

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
    self.revlink = None
    self.committer = None
    self.comment = None
    self.details = None
    # Per-builder status stored at self.status[master][category][builder].
    self.status = {}
    self.timestamp = datetime.datetime.now()

  def purge_unicode(self, enc='ascii', err='replace'):
    self.committer = self.committer.encode(enc, err)
    self.comment = self.comment.encode(enc, err)
    self.details = self.details.encode(enc, err)

class MergerData(object):
  """Persistent data storage class.

  Holds all of the data we have about the last 100 revisions.
  Keeps it organized and can render it upon request.
  """

  def __init__(self):
    self.SIZE = 100
    # Straight list of masters to display.
    self.ordered_masters = app.DEFAULT_MASTERS_TO_MERGE
    # Ordered categories, indexed by master.
    self.ordered_categories = {}
    # Ordered builders, indexed by master and category.
    self.ordered_builders = {}
    self.latest_rev = 0
    self.rows = {}
    self.status = {}
    self.failures = {}

  def bootstrap(self):
    """Fills an empty MergerData with 100 rows of data."""
    # Populate the categories, masters, status, and failures data.
    for m in self.ordered_masters:
      for d in (self.ordered_builders,
                self.ordered_categories,
                self.status,
                self.failures):
        d.setdefault(m, {})
      # Get the category data and construct the list of categories
      # for this master.
      category_data = app.get_and_cache_pagedata('%s/console/categories' % m)
      if not category_data['content']:
        category_list = [u'default']
      else:
        category_soup = BeautifulSoup(category_data['content'])
        category_list = [tag.string.strip() for tag in
                         category_soup.findAll('td', 'DevStatus')]
      self.ordered_categories[m] = category_list
      # Get the builder status data.
      builder_data = app.get_and_cache_pagedata('%s/console/summary' % m)
      if not builder_data['content']:
        continue
      builder_soup = BeautifulSoup(builder_data['content'])
      builders_by_category = builder_soup.tr.findAll('td', 'DevSlave',
                                                     recursive=False)
      # Construct the list of builders for this category.
      for i, c in enumerate(self.ordered_categories[m]):
        self.ordered_builders[m].setdefault(c, {})
        builder_list = [tag['title'] for tag in
                        builders_by_category[i].findAll('a', 'DevSlaveBox')]
        self.ordered_builders[m][c] = builder_list
      # Fill in the status data for all of this master's builders.
      update_status(m, builder_data['content'], self.status)
      # Copy that status data over into the failures dictionary too.
      for c in self.ordered_categories[m]:
        self.failures[m].setdefault(c, {})
        for b in self.ordered_builders[m][c]:
          if self.status[m][c][b] not in ('success', 'running', 'notstarted'):
            self.failures[m][c][b] = True
          else:
            self.failures[m][c][b] = False
    # Populate the individual row data, saving status info in the same
    # master/category/builder tree format constructed above.
    latest_rev = int(app.get_and_cache_rowdata('latest_rev')['rev_number'])
    if not latest_rev:
      logging.error("MergerData.bootstrap(): Didn't get latest_rev. Aborting.")
      return
    n = latest_rev
    num_rows_saved = num_rows_skipped = 0
    while num_rows_saved < self.SIZE and num_rows_skipped < 10:
      curr_row = RowData()
      for m in self.ordered_masters:
        update_row(n, m, curr_row)
      # If we didn't get any data, that revision doesn't exist, so skip on.
      if not curr_row.revision:
        num_rows_skipped += 1
        n -= 1
        continue
      self.rows[n] = curr_row
      num_rows_skipped = 0
      num_rows_saved += 1
      n -= 1
    self.latest_rev = max(self.rows.keys())


def update_row(revision, master, row):
  """Fetches a row from the datastore and puts it in a RowData object."""
  # Fetch the relevant data from the datastore / cache.
  row_data = app.get_and_cache_rowdata('%s/console/%s' % (master, revision))
  if not row_data:
    return
  # Only grab the common data from the main master.
  if master == 'chromium.main':
    row.revision = int(row_data['rev_number'])
    row.revlink = row_data['rev']
    row.committer = row_data['name']
    row.comment = row_data['comment']
    row.details = row_data['details']
  row.status.setdefault(master, {})
  update_status(master, row_data['status'], row.status)


def update_status(master, status_html, status_dict):
  """Parses build status information and saves it to a status dictionary."""
  builder_soup = BeautifulSoup(status_html)
  builders_by_category = builder_soup.findAll('table')
  for i, c in enumerate(data.ordered_categories[master]):
    status_dict[master].setdefault(c, {})
    statuses_by_builder = builders_by_category[i].findAll('td',
                                                          'DevStatusBox')
    # If we didn't get anything, it's because we're parsing the overall
    # summary, so look for Slave boxes instead of Status boxes.
    if not statuses_by_builder:
      statuses_by_builder = builders_by_category[i].findAll('td',
                                                            'DevSlaveBox')
    for j, b in enumerate(data.ordered_builders[master][c]):
      # Save the whole link as the status to keep ETA and build number info.
      status = unicode(statuses_by_builder[j].a)
      status_dict[master][c][b] = status


def notstarted(status):
  """Converts a DevSlave status box to a notstarted DevStatus box."""
  status_soup = BeautifulSoup(status)
  status_soup['class'] = 'DevStatusBox notstarted'
  return unicode(status_soup)


class MergerUpdateAction(base_page.BasePage):
  """Handles update requests.

  Takes data gathered by the cronjob and pulls it into active memory.
  """

  def get(self):
    latest_rev = int(app.get_and_cache_rowdata('latest_rev')['rev_number'])
    # We may have brand new rows, so store them.
    if latest_rev not in data.rows:
      for n in xrange(data.latest_rev + 1, latest_rev + 1):
        curr_row = RowData()
        for m in data.ordered_masters:
          update_row(n, m, curr_row)
        # If we didn't get any data, that revision doesn't exist, so skip on.
        if not curr_row.revision:
          continue
        data.rows[n] = curr_row
    # Update our stored latest_rev to reflect the new data.
    data.latest_rev = max(data.rows.keys())
    # Now update the status of the rest of the rows.
    offset = 0
    while offset < data.SIZE:
      n = data.latest_rev - offset
      if n not in data.rows:
        offset += 1
        continue
      curr_row = data.rows[n]
      for m in data.ordered_masters:
        row_data = app.get_and_cache_rowdata('%s/console/%s' % (m, n))
        if not row_data:
          continue
        update_status(m, row_data['status'], curr_row.status)
      offset += 1
    # Finally delete any extra rows that we don't want to keep around.
    if len(data.rows) > data.SIZE:
      old_revs = sorted(data.rows.keys(), reverse=True)[data.SIZE:]
      for rev in old_revs:
        del data.rows[rev]
    self.response.out.write('Update completed (rows %s - %s).' %
                            (min(data.rows.keys()), max(data.rows.keys())))


class MergerRenderAction(base_page.BasePage):

  def get(self):
    class TemplateData(object):
      def __init__(self, rhs, numrevs):
        self.ordered_rows = sorted(rhs.rows.keys(), reverse=True)[:numrevs]
        self.ordered_masters = rhs.ordered_masters
        self.ordered_categories = rhs.ordered_categories
        self.ordered_builders = rhs.ordered_builders
        self.status = rhs.status
        self.rows = {}
        for row in self.ordered_rows:
          self.rows[row] = rhs.rows[row].purge_unicode()
        self.category_count = sum([len(self.ordered_categories[master])
                                   for master in self.ordered_masters])
    num_revs = self.request.get('numrevs')
    if num_revs:
      num_revs = utils.clean_int(num_revs, -1)
    if not num_revs or num_revs <= 0:
      num_revs = 25
    out = TemplateData(data, num_revs)
    template = template_environment.get_template('merger_b.html')
    self.response.out.write(template.render(data=out))


# Summon our persistent data model into existence.
data = MergerData()
data.bootstrap()
template_environment = jinja2.Environment()
template_environment.loader = jinja2.FileSystemLoader('templates')
template_environment.filters['notstarted'] = notstarted


URLS = [
    ('/restricted/merger/update',     MergerUpdateAction),
    ('/restricted/merger/render.*',   MergerRenderAction),
]

application = webapp2.WSGIApplication(URLS, debug=True)
