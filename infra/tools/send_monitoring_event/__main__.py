# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import sys
import traceback

from infra_libs import app
from infra_libs import event_mon
from infra_libs import ts_mon

from infra.tools.send_monitoring_event import common


success_metric = ts_mon.BooleanMetric('send_monitoring_event/success',
    'Set to True if the monitoring event was sent successfully',
    None)


class SendMonitoringEvent(app.BaseApplication):
  DESCRIPTION = """Send an event to the monitoring pipeline.

    Examples:
    run.py infra.tools.send_monitoring_event --service-event-type=START \\
                                     --service-event-revinfo <filename>

    run.py infra.tools.send_monitoring_event \\
                                     --service-event-stack-trace "<stack trace>"

    run.py infra.tools.send_monitoring_event --build-event-type=SCHEDULER \\
                                     --build-event-build-name=foo
                                     --build-event-hostname='bot.dns.name'
    """
  def add_argparse_options(self, parser):
    super(SendMonitoringEvent, self).add_argparse_options(parser)
    common.add_argparse_options(parser)

    parser.set_defaults(
        ts_mon_flush='manual',
        ts_mon_target_type='task',
        ts_mon_task_service_name='send_monitoring_event',
        ts_mon_task_job_name='manual',
      )

  def process_argparse_options(self, opts):
    super(SendMonitoringEvent, self).process_argparse_options(opts)
    common.process_argparse_options(opts)

  def main(self, opts):  # pragma: no cover
    status = 0

    try:
      if opts.build_event_type:
        success_metric.set(common.send_build_event(opts))

      elif opts.service_event_type:
        success_metric.set(common.send_service_event(opts))

      elif opts.events_from_file:
        success_metric.set(common.send_events_from_file(opts))

      else:
        print >> sys.stderr, ('At least one of the --*-event-type options or '
                              '--events-from-file should be provided. Nothing '
                              'was sent.')
        status = 2
        success_metric.set(False)
    except Exception:
      success_metric.set(False)
      traceback.print_exc()  # helps with debugging locally.
    finally:
      event_mon.close()
      try:
        ts_mon.flush()
      except ts_mon.MonitoringNoConfiguredMonitorError:
        logging.error("Unable to flush ts_mon because it's not configured.")
      except Exception:
        logging.exception("Flushing ts_mon metrics failed.")
    return status


if __name__ == '__main__':
  SendMonitoringEvent().run()
