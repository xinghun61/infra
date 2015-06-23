# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import glob
import logging
import os
import json
import sys

from infra_libs import event_mon
import infra_libs.logs


LOGGER = logging.getLogger(__name__)


def get_arguments(argv):
  """Process command-line arguments.

  Args:
    argv (list of strings): sys.argv[1:]
  Returns:
    args (argparse.Namespace): processed command-line arguments
  """
  # This function must be testable. Put non-testable side-effects
  # in main().

  parser = argparse.ArgumentParser(
    description="""Send an event to the monitoring pipeline.

    Examples:
    run.py infra.tools.send_monitoring_event --service-event-type=START \\
                                     --service-event-revinfo <filename>

    run.py infra.tools.send_monitoring_event \\
                                     --service-event-stack-trace "<stack trace>"

    run.py infra.tools.send_monitoring_event --build-event-type=SCHEDULER \\
                                     --build-event-build-name=foo
                                     --build-event-hostname='bot.dns.name'
    """, formatter_class=argparse.RawTextHelpFormatter)

  # Common fields
  common_group = parser.add_argument_group('Common event options')
  common_group.add_argument('--event-mon-timestamp-kind',
                            choices=[kind
                                     for kind in event_mon.TIMESTAMP_KINDS
                                     if kind],
                            default='POINT',
                            help='General kind of event. This value is used '
                            'e.g. to\nautomatically compute durations between '
                            'START and STOP\nevents. Default: %(default)s')
  common_group.add_argument('--event-mon-event-timestamp', type=int,
                            help='Timestamp when the event was generated, as '
                            'number of\nmilliseconds since the Unix EPOCH.'
                            '\nDefaults to current time.')

  # Service event
  service_group = parser.add_argument_group('Service event options')
  type_group = service_group.add_mutually_exclusive_group()
  type_group.add_argument('--service-event-type',
                      choices=event_mon.EVENT_TYPES,
                      help='Kind of event to send.')

  type_group.add_argument('--service-event-stack-trace',
                          metavar='STACK_TRACE',
                          help='String containing a stack trace. Sets the event'
                          ' type\nto "CRASH" automatically.')

  revinfo = service_group.add_mutually_exclusive_group()
  revinfo.add_argument('--service-event-revinfo',
                       metavar='FILENAME',
                       help='File to read revision information from, "-" means'
                       '\nstandard input. The file'
                       ' is supposed to contain the\noutput of'
                       ' "gclient revinfo -a".')
  revinfo.add_argument('--service-event-revinfo-from-gclient',
                       action='store_true',
                       help='Calls gclient to get revision information. '
                       '\nMutually exclusive with --service-event-revinfo')

  # Build events
  build_group = parser.add_argument_group('Build event options')
  build_group.add_argument('--build-event-type',
                           choices=event_mon.BUILD_EVENT_TYPES,
                           help='Type of the build event.')
  build_group.add_argument('--build-event-hostname',
                           metavar='HOSTNAME',
                           help='Hostname of the bot running the build.')
  build_group.add_argument('--build-event-build-name',
                           metavar='BUILDER_NAME',
                           help='Builder name as known to Buildbot.')
  build_group.add_argument('--build-event-build-number',
                           type=int,
                           metavar='BUILD_NUMBER',
                           help='Build number as known to Buildbot')
  build_group.add_argument('--build-event-build-scheduling-time',
                           type=int,
                           metavar='TIMESTAMP',
                           help='Timestamp (in milliseconds since the epoch),'
                           ' when the\nbuild was scheduled. Used to tell '
                           'apart builds with\n identical build numbers.')
  build_group.add_argument('--build-event-step-name',
                           metavar='STEP_NAME',
                           help='Step name as known to Buildbot.')
  build_group.add_argument('--build-event-step-number',
                           type=int,
                           metavar='BUILD_NUMBER',
                           help='Step number inside the build. Zero-based.')
  build_group.add_argument('--build-event-result',
                           choices=event_mon.BUILD_RESULTS,
                           help='Result of build or step depending on '
                           'whether any \n--build-event-step-* options have '
                           'been provided or not.')

  # Read events from file
  file_group = parser.add_argument_group('Read events from file')
  file_group.add_argument('--events-from-file',
                          metavar='FILENAME', nargs='*',
                          help='File containing events as json dict. This '
                          'option\nis incompatible with --build-event-type and'
                          '\n--service-event-type.\nSee '
                          'send_event.read_events_from_file for details\n'
                          'on the format. This options can be passed multiple\n'
                          'times, and wildcards can be used.')
  file_group.add_argument('--delete-file-when-sent',
                          action='store_true', default=False,
                          help='If all events read from a file have been '
                          'successfully\nsent to the endpoint, delete the '
                          'file. By default\nfiles are kept.')


  event_mon.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)

  parser.set_defaults(
      logs_directory='',
  )

  args = parser.parse_args(argv)

  if args.service_event_stack_trace:
    args.service_event_type = 'CRASH'

  if args.build_event_type and args.service_event_type:
    parser.error('Only one type of event can be sent at once. '
                 'Got both --build-event-type and --service-event-type.')
  if ((args.build_event_type and args.events_from_file)
      or (args.service_event_type and args.events_from_file)):
    parser.error('--events-from-file is not compatible with either'
                 '--service-event-type or --build-event-type.')
  return args


def send_service_event(args):
  """Entry point when --service-event-type is passed."""
  revinfo = {}
  if args.service_event_revinfo:
    if args.service_event_revinfo == '-':  # pragma: no cover
      revinfo = event_mon.parse_revinfo(sys.stdin.read())
    else:
      with open(args.service_event_revinfo, 'r') as f:
        revinfo = event_mon.parse_revinfo(f.read())
  elif args.service_event_revinfo_from_gclient:  # pragma: no cover
    revinfo = event_mon.get_revinfo()

  if args.service_event_stack_trace:
    args.service_event_type = 'CRASH'

  event_mon.send_service_event(
    args.service_event_type,
    code_version=revinfo.values(),
    stack_trace=args.service_event_stack_trace,
    timestamp_kind=args.event_mon_timestamp_kind,
    event_timestamp=args.event_mon_event_timestamp)


def send_build_event(args):
  """Entry point when --build-event-type is passed."""
  event_mon.send_build_event(
    args.build_event_type,
    args.build_event_hostname,
    args.build_event_build_name,
    build_number=args.build_event_build_number,
    build_scheduling_time=args.build_event_build_scheduling_time,
    step_name=args.build_event_step_name,
    step_number=args.build_event_step_number,
    result=args.build_event_result,
    timestamp_kind=args.event_mon_timestamp_kind,
    event_timestamp=args.event_mon_event_timestamp)


def send_events_from_file(args):
  """Entry point when --events-from-file is passed."""
  file_list = get_event_file_list(args.events_from_file)

  for filename in file_list:
    LOGGER.info('Processing %s', filename)
    events = read_events_from_file(filename)
    success = event_mon.send_events(events)
    if success:
      if args.delete_file_when_sent:
        LOGGER.info('Events successfully sent. Deleting file %s.', filename)
        try:
          os.remove(filename)
        except OSError: # pragma: no cover
          LOGGER.exception('Failed to delete %s.', filename)
    else: # pragma: no cover
      LOGGER.error('Failed to send events. Keeping file around: %s', filename)


def get_event_file_list(filename_globs):
  file_list = []
  for filename_glob in filename_globs:
    file_list.extend(glob.glob(filename_glob))
  return [os.path.abspath(filename) for filename in file_list]


def read_events_from_file(filename):
  """Read a list of ChromeInfraEvent from a file.

  Each line of the file is expected to contain options in the shape of a dict:

  Example:
  {"build-event-type": "BUILD", "build-event-hostname": "hostname",
   "build-event-build-name": "fake builder"}

  There may be several lines, but each dict should be one its own line.

  Caveat: only build events options are supported so far.
  See send_monitoring_event --help for the full list of flags.

  Args:
    filename(str): path to the file to read.

  Return:
    log_events (iterable of LogRequestLite): events read from the file.
  """
  log_events = []
  with open(filename, 'r') as f:
    for line in f:
      if not line.strip():
        continue
      try:
        args = json.loads(line)
      except ValueError:
        LOGGER.error("Unparseable line in %s: %s", filename, line)
        continue

      if 'build-event-type' in args:
        log_events.append(
          event_mon.get_build_event(
            args.get('build-event-type'),
            args.get('build-event-hostname'),
            args.get('build-event-build-name'),
            build_number=args.get('build-event-build-number'),
            build_scheduling_time=args.get('build-event-build-scheduling-time'),
            step_name=args.get('build-event-step-name'),
            step_number=args.get('build-event-step-number'),
            result=args.get('build-event-result'),
            timestamp_kind=args.get('event-mon-timestamp-kind'),
            event_timestamp=args.get('event-mon-event-timestamp')))

  return log_events
