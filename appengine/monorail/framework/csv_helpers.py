# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for creating CSV pagedata."""

import types

from framework import framework_helpers


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


def RewriteColspec(col_spec):
  """Rewrite the given colspec to expand special CSV columns."""
  new_cols = []

  for col in col_spec.split():
    rewriten_cols = _CSV_COLS_TO_REPLACE.get(col.lower(), [col])
    new_cols.extend(rewriten_cols)

  return ' '.join(new_cols)


def ReformatRowsForCSV(mr, page_data, url_path):
  """Rewrites/adds to the given page_data so the CSV templates can use it."""
  # CSV files are at risk for the PDF content sniffing by Acrobat Reader
  page_data['prevent_sniffing'] = True

  # If we're truncating the results, add a URL to the next page of results
  page_data['next_csv_link'] = None
  pagination = page_data['pagination']
  if pagination.next_url:
    page_data['next_csv_link'] = framework_helpers.FormatAbsoluteURL(
        mr, url_path, start=pagination.last)
    page_data['item_count'] = pagination.last - pagination.start + 1

  for row in page_data['table_data']:
    for cell in row.cells:
      for value in cell.values:
        value.item = EscapeCSV(value.item)
  return page_data


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
