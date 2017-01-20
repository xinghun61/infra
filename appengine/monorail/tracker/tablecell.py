# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that generate value cells in the issue list table."""

import logging
import time
from third_party import ezt

from framework import framework_constants
from framework import table_view_helpers
from tracker import tracker_bizobj

# pylint: disable=unused-argument

class TableCellDateAdded(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing the date added of an issue."""

  def __init__(self, issue, date_added=None, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, [date_added])


class TableCellAdderID(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing an issue's adder_id."""

  def __init__(self, issue, adder_id=None, users_by_id=None, **_kw):
    if adder_id:
      display_name = [users_by_id[adder_id].display_name]
    else:
      display_name = [None]
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR,
        display_name)


class TableCellRank(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue rank."""

  def __init__(self, issue, issue_rank=None, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, [issue_rank])


class TableCellID(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue IDs."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ID, [str(issue.local_id)])


class TableCellStatus(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue status values."""

  def __init__(self, issue, **_kws):
    values = []
    derived_values = []
    if issue.status:
      values = [issue.status]
    if issue.derived_status:
      derived_values = [issue.derived_status]

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, values,
        derived_values=derived_values)


class TableCellOwner(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue owner name."""

  def __init__(self, issue, users_by_id=None, **_kw):
    values = []
    derived_values = []
    if issue.owner_id:
      values = [users_by_id[issue.owner_id].display_name]
    if issue.derived_owner_id:
      derived_values = [users_by_id[issue.derived_owner_id].display_name]

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, values,
        derived_values=derived_values)


class TableCellReporter(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue reporter name."""

  def __init__(self, issue, users_by_id=None, **_kw):
    try:
      values = [users_by_id[issue.reporter_id].display_name]
    except KeyError:
      logging.info('issue reporter %r not found', issue.reporter_id)
      values = ['deleted?']

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, values)


class TableCellCc(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue Cc user names."""

  def __init__(self, issue, users_by_id=None, **_kw):
    values = [users_by_id[cc_id].display_name
              for cc_id in issue.cc_ids]

    derived_values = [users_by_id[cc_id].display_name
                      for cc_id in issue.derived_cc_ids]

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, values,
        derived_values=derived_values)


class TableCellAttachments(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue attachment count."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, [issue.attachment_count],
        align='right')


class TableCellOpened(table_view_helpers.TableCellDate):
  """TableCell subclass specifically for showing issue opened date."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCellDate.__init__(self, issue.opened_timestamp)


class TableCellClosed(table_view_helpers.TableCellDate):
  """TableCell subclass specifically for showing issue closed date."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCellDate.__init__(self, issue.closed_timestamp)


class TableCellModified(table_view_helpers.TableCellDate):
  """TableCell subclass specifically for showing issue modified date."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCellDate.__init__(self, issue.modified_timestamp)


class TableCellOwnerModified(table_view_helpers.TableCellDate):
  """TableCell subclass specifically for showing owner modified age."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCellDate.__init__(
        self, issue.owner_modified_timestamp, days_only=True)


class TableCellStatusModified(table_view_helpers.TableCellDate):
  """TableCell subclass specifically for showing status modified age."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCellDate.__init__(
        self, issue.status_modified_timestamp, days_only=True)


class TableCellComponentModified(table_view_helpers.TableCellDate):
  """TableCell subclass specifically for showing component modified age."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCellDate.__init__(
        self, issue.component_modified_timestamp, days_only=True)


class TableCellOwnerLastVisit(table_view_helpers.TableCellDate):
  """TableCell subclass specifically for showing owner last visit days ago."""

  def __init__(self, issue, users_by_id=None, **_kw):
    owner_view = users_by_id.get(issue.owner_id or issue.derived_owner_id)
    last_visit = None
    if owner_view:
      last_visit = owner_view.user.last_visit_timestamp
    table_view_helpers.TableCellDate.__init__(
        self, last_visit, days_only=True)


class TableCellBlockedOn(table_view_helpers.TableCell):
  """TableCell subclass for listing issues the current issue is blocked on."""

  def __init__(self, issue, related_issues=None, **_kw):
    ref_issues = [related_issues[iid] for iid in issue.blocked_on_iids
                  if iid in related_issues]
    default_pn = issue.project_name
    # TODO(jrobbins): in cross-project searches, leave default_pn = None.
    values = [
        tracker_bizobj.FormatIssueRef(
            (ref_issue.project_name, ref_issue.local_id),
            default_project_name=default_pn)
        for ref_issue in ref_issues]
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, values)


class TableCellBlocking(table_view_helpers.TableCell):
  """TableCell subclass for listing issues the current issue is blocking."""

  def __init__(self, issue, related_issues=None, **_kw):
    ref_issues = [related_issues[iid] for iid in issue.blocking_iids
                  if iid in related_issues]
    default_pn = issue.project_name
    # TODO(jrobbins): in cross-project searches, leave default_pn = None.
    values = [
        tracker_bizobj.FormatIssueRef(
            (ref_issue.project_name, ref_issue.local_id),
            default_project_name=default_pn)
        for ref_issue in ref_issues]
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, values)


class TableCellBlocked(table_view_helpers.TableCell):
  """TableCell subclass for showing whether an issue is blocked."""

  def __init__(self, issue, **_kw):
    if issue.blocked_on_iids:
      value = 'Yes'
    else:
      value = 'No'

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, [value])


class TableCellMergedInto(table_view_helpers.TableCell):
  """TableCell subclass for showing whether an issue is blocked."""

  def __init__(
      self, issue, related_issues=None, **_kw):
    if issue.merged_into:
      ref_issue = related_issues[issue.merged_into]
      ref = ref_issue.project_name, ref_issue.local_id
      default_pn = issue.project_name
      # TODO(jrobbins): in cross-project searches, leave default_pn = None.
      values = [
          tracker_bizobj.FormatIssueRef(ref, default_project_name=default_pn)]
    else:   # Note: None means not merged into any issue.
      values = []

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, values)


class TableCellComponent(table_view_helpers.TableCell):
  """TableCell subclass for showing components."""

  def __init__(self, issue, config=None, **_kw):
    explicit_paths = []
    for component_id in issue.component_ids:
      cd = tracker_bizobj.FindComponentDefByID(component_id, config)
      if cd:
        explicit_paths.append(cd.path)

    derived_paths = []
    for component_id in issue.derived_component_ids:
      cd = tracker_bizobj.FindComponentDefByID(component_id, config)
      if cd:
        derived_paths.append(cd.path)

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, explicit_paths,
        derived_values=derived_paths)


class TableCellAllLabels(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing all labels on an issue."""

  def __init__(self, issue, **_kw):
    values = []
    derived_values = []
    if issue.labels:
      values = issue.labels[:]
    if issue.derived_labels:
      derived_values = issue.derived_labels[:]

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_ATTR, values,
        derived_values=derived_values)


# This maps column names to factories/constructors that make table cells.
# Subclasses can override this mapping, so any additions to this mapping
# should also be added to subclasses.
CELL_FACTORIES = {
    'id': TableCellID,
    'project': table_view_helpers.TableCellProject,
    'component': TableCellComponent,
    'summary': table_view_helpers.TableCellSummary,
    'status': TableCellStatus,
    'owner': TableCellOwner,
    'reporter': TableCellReporter,
    'cc': TableCellCc,
    'stars': table_view_helpers.TableCellStars,
    'attachments': TableCellAttachments,
    'opened': TableCellOpened,
    'closed': TableCellClosed,
    'modified': TableCellModified,
    'blockedon': TableCellBlockedOn,
    'blocking': TableCellBlocking,
    'blocked': TableCellBlocked,
    'mergedinto': TableCellMergedInto,
    'ownermodified': TableCellOwnerModified,
    'statusmodified': TableCellStatusModified,
    'componentmodified': TableCellComponentModified,
    'ownerlastvisit': TableCellOwnerLastVisit,
    'rank': TableCellRank,
    'added': TableCellDateAdded,
    'adder': TableCellAdderID,
    'alllabels': TableCellAllLabels,
    }


# Time format that spreadsheets seem to understand.
# E.g.: "May 19 2008 13:30:23".  Tested with MS Excel 2003,
# OpenOffice.org, NeoOffice, and Google Spreadsheets.
CSV_DATE_TIME_FMT = '%b %d, %Y %H:%M:%S'


def TimeStringForCSV(timestamp):
  """Return a timestamp in a format that spreadsheets understand."""
  return time.strftime(CSV_DATE_TIME_FMT, time.gmtime(timestamp))


class TableCellOpenedCSV(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue opened date."""

  def __init__(self, issue, **_kw):
    date_str = TimeStringForCSV(issue.opened_timestamp)

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE, [date_str])


class TableCellOpenedTimestamp(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue opened timestamp."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE,
        [issue.opened_timestamp])


class TableCellModifiedCSV(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue modified date."""

  def __init__(self, issue, **_kw):
    values = []
    if issue.modified_timestamp:
      values = [TimeStringForCSV(issue.modified_timestamp)]

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE, values)


class TableCellModifiedTimestamp(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue modified timestamp."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE,
        [issue.modified_timestamp])


class TableCellClosedCSV(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue closed date."""

  def __init__(self, issue, **_kw):
    values = []
    if issue.closed_timestamp:
      values = [TimeStringForCSV(issue.closed_timestamp)]

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE, values)


class TableCellClosedTimestamp(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing issue closed timestamp."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE,
        [issue.closed_timestamp])


class TableCellOwnerModifiedCSV(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing owner modified date."""

  def __init__(self, issue, **_kw):
    values = []
    if issue.modified_timestamp:
      values = [TimeStringForCSV(issue.owner_modified_timestamp)]

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE, values)


class TableCellOwnerModifiedTimestamp(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing owner modified timestamp."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE,
        [issue.owner_modified_timestamp])


class TableCellStatusModifiedCSV(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing status modified date."""

  def __init__(self, issue, **_kw):
    values = []
    if issue.modified_timestamp:
      values = [TimeStringForCSV(issue.status_modified_timestamp)]

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE, values)


class TableCellStatusModifiedTimestamp(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing status modified timestamp."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE,
        [issue.status_modified_timestamp])


class TableCellComponentModifiedCSV(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing component modified date."""

  def __init__(self, issue, **_kw):
    values = []
    if issue.modified_timestamp:
      values = [TimeStringForCSV(issue.component_modified_timestamp)]

    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE, values)


class TableCellComponentModifiedTimestamp(table_view_helpers.TableCell):
  """TableCell subclass for showing component modified timestamp."""

  def __init__(self, issue, **_kw):
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE,
        [issue.component_modified_timestamp])


class TableCellOwnerLastVisitDaysAgo(table_view_helpers.TableCell):
  """TableCell subclass specifically for showing owner last visit days ago."""

  def __init__(self, issue, users_by_id=None, **_kw):
    owner_view = users_by_id.get(issue.owner_id or issue.derived_owner_id)
    last_visit_days_ago = None
    if owner_view and owner_view.user.last_visit_timestamp:
      secs_ago = int(time.time()) - owner_view.user.last_visit_timestamp
      last_visit_days_ago = secs_ago / framework_constants.SECS_PER_DAY
    table_view_helpers.TableCell.__init__(
        self, table_view_helpers.CELL_TYPE_UNFILTERABLE, [last_visit_days_ago])


# Maps column names to factories/constructors that make table cells.
# Uses the defaults in issuelist.py but changes the factory for the
# summary cell to properly escape the data for CSV files.
CSV_CELL_FACTORIES = CELL_FACTORIES.copy()
CSV_CELL_FACTORIES.update({
    'opened': TableCellOpenedCSV,
    'openedtimestamp': TableCellOpenedTimestamp,
    'closed': TableCellClosedCSV,
    'closedtimestamp': TableCellClosedTimestamp,
    'modified': TableCellModifiedCSV,
    'modifiedtimestamp': TableCellModifiedTimestamp,
    'ownermodified': TableCellOwnerModifiedCSV,
    'ownermodifiedtimestamp': TableCellOwnerModifiedTimestamp,
    'statusmodified': TableCellStatusModifiedCSV,
    'statusmodifiedtimestamp': TableCellStatusModifiedTimestamp,
    'componentmodified': TableCellComponentModifiedCSV,
    'componentmodifiedtimestamp': TableCellComponentModifiedTimestamp,
    'ownerlastvisitdaysago': TableCellOwnerLastVisitDaysAgo,
    })
