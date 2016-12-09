# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Implemention of the issue list output as a CSV file."""

import types

import settings

from framework import framework_helpers
from framework import permissions
from framework import urls
from tracker import issuelist
from tracker import tablecell
from tracker import tracker_constants


class IssueListCsv(issuelist.IssueList):
  """IssueListCsv provides to the user a list of issues as a CSV document.

  Overrides the standard IssueList servlet but uses a different EZT template
  to provide the same content as the IssueList only as CSV.  Adds the HTTP
  header to offer the result as a download.
  """

  _PAGE_TEMPLATE = 'tracker/issue-list-csv.ezt'

  def GatherPageData(self, mr):
    if not mr.auth.user_id:
      raise permissions.PermissionException(
          'Anonymous users are not allowed to download issue list CSV')

    # Sets headers to allow the response to be downloaded.
    self.content_type = 'text/csv; charset=UTF-8'
    download_filename = '%s-issues.csv' % mr.project_name
    self.response.headers.add(
        'Content-Disposition', 'attachment; filename=%s' % download_filename)
    self.response.headers.add('X-Content-Type-Options', 'nosniff')

    # Rewrite the colspec to add some extra columns that make the CSV
    # file more complete.
    with self.profiler.Phase('finishing config work'):
      config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    mr.ComputeColSpec(config)
    mr.col_spec = _RewriteColspec(mr.col_spec)
    page_data = issuelist.IssueList.GatherPageData(self, mr)

    # CSV files are at risk for PDF content sniffing by Acrobat Reader.
    page_data['prevent_sniffing'] = True

    # If we're truncating the results, add a URL to the next page of results
    page_data['next_csv_link'] = None
    pagination = page_data['pagination']
    if pagination.next_url:
      page_data['next_csv_link'] = framework_helpers.FormatAbsoluteURL(
          mr, urls.ISSUE_LIST_CSV, start=pagination.last)
      page_data['item_count'] = pagination.last - pagination.start + 1

    # Escape values to prevent exploits in a spreadsheet app.
    for row in page_data['table_data']:
      for cell in row.cells:
        for value in cell.values:
          value.item = EscapeCSV(value.item)

    return page_data

  def GetCellFactories(self):
    return tablecell.CSV_CELL_FACTORIES


# Whenever the user request one of these columns, we replace it with the
# list of alternate columns.  In effect, we split the requested column
# into two CSV columns.
_CSV_COLS_TO_REPLACE = {
    'summary': ['Summary', 'AllLabels'],
    'opened': ['Opened', 'OpenedTimestamp'],
    'closed': ['Closed', 'ClosedTimestamp'],
    'modified': ['Modified', 'ModifiedTimestamp'],
    'ownermodified': ['OwnerModified', 'OwnerModifiedTimestamp'],
    'statusmodified': ['StatusModified', 'StatusModifiedTimestamp'],
    'componentmodified': ['ComponentModified', 'ComponentModifiedTimestamp'],
    'ownerlastvisit': ['OwnerLastVisit', 'OwnerLastVisitDaysAgo'],
    }


def _RewriteColspec(col_spec):
  """Rewrite the given colspec to expand special CSV columns."""
  new_cols = []

  for col in col_spec.split():
    rewriten_cols = _CSV_COLS_TO_REPLACE.get(col.lower(), [col])
    new_cols.extend(rewriten_cols)

  return ' '.join(new_cols)


def EscapeCSV(s):
  """Return a version of string S that is safe as part of a CSV file."""
  if s is None:
    return ''
  if isinstance(s, types.StringTypes):
    s = s.strip().replace('"', '""')
    # Prefix any formula cells because some spreadsheets have built-in
    # formila functions that can actually have side-effects on the user's
    # computer.
    if s.startswith(('=', '-', '+', '@')):
      s = "'" + s

  return s

