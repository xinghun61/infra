# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import timedelta
import logging

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model import revert_cl_status
from model.tree_closure import TreeClosure
from model.wf_suspected_cl import WfSuspectedCL

_NOT_AVAILABLE = 'N/A'
_DEFAULT_PAGE_SIZE = 1000


def _CalculateMetrics(numbers):
  # (https://crbug.com/720186) Workaround the error in running Findit locally.
  import numpy
  return {
      'average': (time_util.SecondsToHMS(numpy.average(numbers))
                  if numbers else _NOT_AVAILABLE),
      'total':
          len(numbers),
      'ninetieth_percentile': (
          time_util.SecondsToHMS(numpy.percentile(numbers, 90))
          if numbers else _NOT_AVAILABLE),
      'seventieth_percentile': (
          time_util.SecondsToHMS(numpy.percentile(numbers, 70))
          if numbers else _NOT_AVAILABLE),
      'fiftieth_percentile': (
          time_util.SecondsToHMS(numpy.percentile(numbers, 50))
          if numbers else _NOT_AVAILABLE)
  }


def _GenerateFinditMetrics(suspected_cls):
  revert_cls_created = 0
  revert_cls_detected = 0
  revert_cls_committed = 0
  duplicate_revert_cls = 0
  false_positives = 0
  slower_than_sheriff_times = []
  faster_than_sheriff_times = []

  for suspected_cl in suspected_cls:
    revert_cl = suspected_cl.revert_cl
    sheriff_action_time = suspected_cl.sheriff_action_time

    if not revert_cl and not suspected_cl.should_be_reverted:
      continue

    revert_cls_detected += 1

    if revert_cl:
      # Findit proposed a reverting cl.
      revert_cls_created += 1

      if revert_cl.status == revert_cl_status.FALSE_POSITIVE:
        false_positives += 1
      else:
        if revert_cl.status == revert_cl_status.COMMITTED:
          # The sheriff committed Findit's reverting cl.
          revert_cls_committed += 1
        else:
          # Duplicate: Findit was correct but the sheriff made their own revert
          # CL.
          duplicate_revert_cls += 1

        if not sheriff_action_time:  # pragma: no cover
          logging.error(('Findit marked suspectedCL %s as needing revert with '
                         'sheriff reverting but sheriff_action_time not set'),
                        suspected_cl)
          continue

        if revert_cl.created_time < sheriff_action_time:
          time_delta = sheriff_action_time - revert_cl.created_time
          faster_than_sheriff_times.append(time_delta.total_seconds())
        else:
          time_delta = revert_cl.created_time - sheriff_action_time
          slower_than_sheriff_times.append(time_delta.total_seconds())

    elif suspected_cl.should_be_reverted:  # pragma: no branch
      # Findit would have created a reverting cl, but the sheriff was faster.
      if not sheriff_action_time:  # pragma: no cover
        logging.error(('Findit marked suspectedCL %s as needing revert with '
                       'sheriff being faster but sheriff_action_time not set'),
                      suspected_cl)
        continue

      # Fallback to updated_time if cr_notification_time is not set.
      findit_time = (suspected_cl.cr_notification_time or
                     suspected_cl.updated_time)
      time_delta = findit_time - sheriff_action_time
      slower_than_sheriff_times.append(time_delta.total_seconds())

  return {
      'revert_cls_detected':
          revert_cls_detected,
      'revert_cls_created':
          revert_cls_created,
      'revert_cls_committed':
          revert_cls_committed,
      'duplicate_revert_cls':
          duplicate_revert_cls,
      'sheriffs_faster':
          len(slower_than_sheriff_times),
      'findit_faster':
          len(faster_than_sheriff_times),
      'false_positives':
          false_positives,
      'faster_than_sheriff_metrics':
          _CalculateMetrics(faster_than_sheriff_times),
      'slower_than_sheriff_metrics':
          _CalculateMetrics(slower_than_sheriff_times)
  }


def _GetAnalysesWithinDateRange(start_date,
                                end_date,
                                page_size=_DEFAULT_PAGE_SIZE):
  all_suspected_cls = []
  more = True
  cursor = None

  while more:
    suspected_cls, cursor, more = WfSuspectedCL.query(
        WfSuspectedCL.identified_time >= start_date,
        WfSuspectedCL.identified_time < end_date).fetch_page(
            page_size, start_cursor=cursor)
    all_suspected_cls.extend(suspected_cls)

  return all_suspected_cls


def _GenerateTreeClosureMetrics(tree_name, step_name, start_date, end_date):
  query = TreeClosure.query(
      TreeClosure.tree_name == tree_name, TreeClosure.step_name == step_name,
      TreeClosure.closed_time >= start_date, TreeClosure.closed_time < end_date)

  all_closures = list(query)  # Run the query and convert results to a list.

  # Interesting closures are automatically closed but manually opened.
  closures = filter(lambda c: c.auto_closed and not c.auto_opened, all_closures)
  flakes = filter(lambda c: c.possible_flake, closures)
  reverts = filter(lambda c: c.has_revert, closures)

  return {
      'total': len(all_closures),
      'manually_closed_or_auto_opened': len(all_closures) - len(closures),
      'flakes': len(flakes),
      'reverts': len(reverts),
      'others': len(closures) - len(flakes) - len(reverts),
  }


class AutoRevertMetrics(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):  # pragma: no cover
    """Shows the metrics of revert CLs created."""
    start = self.request.get('start_date')
    end = self.request.get('end_date')

    if not start and not end:
      # Default to 1 week of data, starting from 1 day before the most previous
      # midnight.
      previous_utc_midnight = time_util.GetMostRecentUTCMidnight()
      start_date = previous_utc_midnight - timedelta(days=8)
      end_date = previous_utc_midnight - timedelta(days=1)
    else:
      start_date, end_date = time_util.GetStartEndDates(start, end)

    suspected_cls = _GetAnalysesWithinDateRange(start_date, end_date)
    data = _GenerateFinditMetrics(suspected_cls)
    data['tree_closures'] = _GenerateTreeClosureMetrics('chromium', 'compile',
                                                        start_date, end_date)
    data['start_date'] = time_util.FormatDatetime(start_date)
    data['end_date'] = time_util.FormatDatetime(end_date)

    return {'template': 'auto_revert_metrics.html', 'data': data}
