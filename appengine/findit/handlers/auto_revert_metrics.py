# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
from datetime import time
from datetime import timedelta
import logging
import numpy

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import time_util
from model import revert_cl_status
from model.wf_suspected_cl import WfSuspectedCL


_NOT_AVAILABLE = 'N/A'


def _CalculateMetrics(numbers):
  return {
      'average': (
          time_util.SecondsToHMS(numpy.average(numbers)) if numbers else
          _NOT_AVAILABLE),
      'total': len(numbers),
      'ninetieth_percentile': (
          time_util.SecondsToHMS(numpy.percentile(numbers, 90)) if numbers else
          _NOT_AVAILABLE),
      'seventieth_percentile': (
          time_util.SecondsToHMS(numpy.percentile(numbers, 70)) if numbers else
          _NOT_AVAILABLE),
      'fiftieth_percentile': (
          time_util.SecondsToHMS(numpy.percentile(numbers, 50)) if numbers else
          _NOT_AVAILABLE)
  }


def _GenerateMetrics(suspected_cls):
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

      time_delta = (
          suspected_cl.identified_time - suspected_cl.sheriff_action_time)
      slower_than_sheriff_times.append(time_delta.total_seconds())

  return {
      'revert_cls_detected': revert_cls_detected,
      'revert_cls_created': revert_cls_created,
      'revert_cls_committed': revert_cls_committed,
      'duplicate_revert_cls': duplicate_revert_cls,
      'sheriffs_faster': len(slower_than_sheriff_times),
      'findit_faster': len(faster_than_sheriff_times),
      'false_positives': false_positives,
      'faster_than_sheriff_metrics': _CalculateMetrics(
          faster_than_sheriff_times),
      'slower_than_sheriff_metrics': _CalculateMetrics(
          slower_than_sheriff_times)
  }


class AutoRevertMetrics(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):  # pragma: no cover
    """Shows the metrics of revert CLs created."""
    # Only consider results in the past 7-day window beginning 24 hours ago.
    midnight_today = datetime.combine(time_util.GetUTCNow(), time.min)
    start_date = midnight_today - timedelta(days=8)
    end_date = midnight_today - timedelta(days=1)

    suspected_cls = WfSuspectedCL.query(
        WfSuspectedCL.identified_time >= start_date,
        WfSuspectedCL.identified_time < end_date).fetch()

    data = _GenerateMetrics(suspected_cls)

    # TODO(lijeffrey): Add date picker UI.
    data['start_date'] = time_util.FormatDatetime(start_date)
    data['end_date'] = time_util.FormatDatetime(end_date)

    return {
        'template': 'auto_revert_metrics.html',
        'data': data
    }
