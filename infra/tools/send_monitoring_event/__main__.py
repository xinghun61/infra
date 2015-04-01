# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import sys
import infra.libs.event_mon as event_mon
import infra.libs.logs as infra_logs


def get_arguments(argv):
  """Process command-line arguments

  Args:
    argv (list of strings): sys.argv[1:]
  Returns:
    args (argparse.Namespaces): processed command-line arguments
  """
  # This function must be testable. Put non-testable side-effects
  # in main().

  parser = argparse.ArgumentParser(
    description="""Send an event to the monitoring pipeline.

    Examples:
    run.py infra.tool.send_monitoring_event --service-event-type=START \\
                                            --service-event-revinfo <filename>

    run.py infra.tool.send_monitoring_event --service-event-stack-trace \\
                                            "<stack trace>"
    """, formatter_class=argparse.RawTextHelpFormatter)

  service_group = parser.add_argument_group('Service event options')
  type_group = service_group.add_mutually_exclusive_group()
  type_group.add_argument('--service-event-type',
                      choices=event_mon.EVENT_TYPES,
                      default='START',
                      help='Kind of event to send.')

  type_group.add_argument('--service-event-stack-trace',
                          metavar='STACK_TRACE',
                          help='String containing a stack trace. Sets the event'
                          ' type to "CRASH" automatically.')

  revinfo = service_group.add_mutually_exclusive_group()
  revinfo.add_argument('--service-event-revinfo',
                       metavar='FILENAME',
                       help='File to read revision information from, "-" means'
                       ' standard input. The file'
                       ' is supposed to contain the output of'
                       ' "gclient revinfo -a".')
  revinfo.add_argument('--service-event-revinfo-from-gclient',
                       action='store_true',
                       help='Calls gclient to get revision information. '
                       'Mutually exclusive with --service-event-revinfo')

  event_mon.add_argparse_options(parser)
  infra_logs.add_argparse_options(parser)

  args = parser.parse_args(argv)
  return args


def main(argv):  # pragma: no cover
  args = get_arguments(argv)
  event_mon.process_argparse_options(args)
  infra_logs.process_argparse_options(args)

  revinfo = {}
  if args.service_event_revinfo:
    if args.service_event_revinfo == '-':
      revinfo = event_mon.parse_revinfo(sys.stdin.read())
    else:
      with open(args.service_event_revinfo, 'r') as f:
        revinfo = event_mon.parse_revinfo(f.read())
  elif args.service_event_revinfo_from_gclient:
    revinfo = event_mon.get_revinfo()

  if args.service_event_stack_trace:
    args.service_event_type = 'CRASH'
  event_mon.send_service_event(args.service_event_type,
                               code_version=revinfo.values(),
                               stack_trace=args.service_event_stack_trace)
  event_mon.close()


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
