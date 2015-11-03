# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import sys
import traceback

import infra_libs.event_mon as event_mon
import infra_libs.ts_mon as ts_mon

from infra.tools.send_monitoring_event import send_event


def main(argv):  # pragma: no cover
  # Does nothing when no arguments are passed, to make it safe to import this
  # module (main() is executed on import, because this file is called __main__).
  status = 0

  if len(argv) == 0:
    return status

  success_metric = ts_mon.BooleanMetric('send_monitoring_event/success')

  try:
    args = send_event.get_arguments(argv)
    send_event.process_argparse_options(args)

    if args.build_event_type:
      success_metric.set(send_event.send_build_event(args))

    elif args.service_event_type:
      success_metric.set(send_event.send_service_event(args))

    elif args.events_from_file:
      success_metric.set(send_event.send_events_from_file(args))

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
  sys.exit(main(sys.argv[1:]))
