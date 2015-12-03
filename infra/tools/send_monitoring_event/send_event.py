# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import glob
import json
import logging
import os
import re
import sys

from infra_libs import event_mon
from infra_libs import ts_mon
import infra_libs.logs

from infra_libs.event_mon.protos.log_request_lite_pb2 import LogRequestLite
from infra_libs.event_mon.protos.chrome_infra_log_pb2 import ChromeInfraEvent
from infra_libs.event_mon.protos.goma_stats_pb2 import GomaStats

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
                            choices=event_mon.TIMESTAMP_KINDS,
                            help='General kind of event. This value is used '
                            'e.g. to\nautomatically compute durations between '
                            'START and STOP\nevents.')
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

  build_group.add_argument('--build-event-extra-result-code',
                           help='Extra result code. String, comma-separated '
                           'list of strings or json-encoded list of string. '
                           'Each one must be less than 20 characters long.')

  build_group.add_argument('--build-event-goma-stats-path',
                           metavar='FILENAME',
                           help='File containing a serialized GomaStats '
                           'protobuf.')
  build_group.add_argument('--build-event-goma-error',
                           choices=event_mon.GOMA_ERROR_TYPES,
                           help='Reason for no GomaStats protobuf.')
  build_group.add_argument('--build-event-goma-crash-report-id-path',
                           metavar='FILENAME',
                           help='File containing a crash report id.')

  # Read events from file
  file_group = parser.add_argument_group('Read events from file')
  file_group.add_argument('--events-from-file',
                          metavar='FILENAME', nargs='*',
                          help='File containing events as json dict. This '
                          'option\nis incompatible with --build-event-type and'
                          '\n--service-event-type.\nSee '
                          'send_event.read_events_from_file for details\n'
                          'on the format. This option can be passed multiple\n'
                          'times, and wildcards can be used.')
  file_group.add_argument('--delete-file-when-sent',
                          action='store_true', default=False,
                          help='If all events read from a file have been '
                          'successfully\nsent to the endpoint, delete the '
                          'file. By default\nfiles are kept. This does not '
                          'affect the file pointed to by '
                          '--event-logrequest-path')

  file_group.add_argument('--event-logrequest-path',
                          metavar='FILENAME',
                          help='File containing a serialized LogRequestLite'
                          'proto, containing a single ChromeInfraEvent that '
                          'will be used as the default event. Such a file can '
                          'be generated by passing "file" to '
                          '--event-mon-run-type.')

  ts_mon.add_argparse_options(parser)
  event_mon.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)

  parser.set_defaults(
      ts_mon_flush='manual',
      ts_mon_target_type='task',
      ts_mon_task_service_name='send_monitoring_event',
      ts_mon_task_job_name='manual',
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

  # Convert extra_result_code to a list when needed.
  if args.build_event_extra_result_code:
    extra_result_code = args.build_event_extra_result_code.strip()
    if extra_result_code.startswith('['):
      extra_result_code = json.loads(extra_result_code)
    elif ',' in extra_result_code:
      extra_result_code = extra_result_code.split(',')
    args.build_event_extra_result_code = extra_result_code

  return args


def _process_logrequest_path(args):
  """Sets the default event based on --event-logrequest-path.

  This function raises exceptions because if the base event is wrong, then it's
  not worth sending anything anyway.
  """
  if args.event_logrequest_path:
    try:
      with open(args.event_logrequest_path, 'rb') as f:
        request = LogRequestLite.FromString(f.read())

      if len(request.log_event) == 1:
        default_event = ChromeInfraEvent.FromString(
          request.log_event[0].source_extension)
        # Assume that the content is sane because we don't want to duplicate
        # any business logic here.
        # TODO(pgervais): find a better solution.
        event_mon.set_default_event(default_event)
      else:
        raise ValueError(
          'Expected only one log_event in the LogRequestLite proto '
          'pointed by --event-logrequest-path. Found %d in %s',
          len(request.log_event), args.event_logrequest_path)
    except Exception:
      LOGGER.exception('Failure when reading/parsing file %s',
                       args.event_logrequest_path)
      raise

  default_event = event_mon.get_default_event()

  # When the default event is set using --event-logrequest-path, passing
  # --build-event-type or --service-event-type is optional. These options
  # still takes precedence but they must keep the event type the same.
  if (default_event.build_event.HasField('type') and
      default_event.service_event.HasField('type')):
    msg = ('Default event contains both service_event_type and '
           'build_event_type which is incorrect. Make sure you passed '
           'a correct proto to --event-logrequest-path. Otherwise it\'s an '
           'internal error. Aborting.')
    LOGGER.error(msg)
    raise ValueError(msg)

  if default_event.build_event.HasField('type'):
    if args.service_event_type:
      msg = ('The default event contains a type for build_event, but a '
             'service_event type was provided on the command-line. At most '
             'one of them can be specified. Aborting.')
      LOGGER.error(msg)
      raise ValueError(msg)

    if not args.build_event_type:
      args.build_event_type = event_mon.BuildEvent.BuildEventType.Name(
        default_event.build_event.type)

  if default_event.service_event.HasField('type'):
    if args.build_event_type:
      msg = ('The default event contains a type for service_event, but a '
             'build_event type was provided on the command-line. At most '
             'one of them can be specified. Aborting.')
      LOGGER.error(msg)
      raise ValueError(msg)
    if not args.service_event_type:
      args.service_event_type = event_mon.ServiceEvent.ServiceEventType.Name(
        default_event.service_event.type)


def process_argparse_options(args):  # pragma: no cover
  infra_libs.logs.process_argparse_options(args)
  event_mon.process_argparse_options(args)
  # Put here because we want to send the presence metric as late as possible.
  ts_mon.process_argparse_options(args)
  _process_logrequest_path(args)


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

  return bool(event_mon.send_service_event(
    args.service_event_type,
    code_version=revinfo.values(),
    stack_trace=args.service_event_stack_trace,
    timestamp_kind=args.event_mon_timestamp_kind,
    event_timestamp=args.event_mon_event_timestamp))


def send_build_event(args):
  """Entry point when --build-event-type is passed."""
  goma_stats = None
  if args.build_event_goma_stats_path:
    try:
      with open(args.build_event_goma_stats_path, 'rb') as f:
        goma_stats = GomaStats.FromString(f.read())
    except Exception:
      LOGGER.exception('Failure when reading/parsing file %s',
                       args.build_event_goma_stats_path)
      raise

  goma_crash_report_id = None
  if args.build_event_goma_crash_report_id_path:
    try:
      with open(args.build_event_goma_crash_report_id_path, 'r') as f:
        goma_crash_report_id = f.read().strip()
    except Exception:  # pragma: no cover
      LOGGER.exception('Failure when reading/parsing file %s',
                       args.build_event_goma_crash_report_id_path)
      raise

  return bool(event_mon.send_build_event(
    args.build_event_type,
    args.build_event_hostname,
    args.build_event_build_name,
    build_number=args.build_event_build_number,
    build_scheduling_time=args.build_event_build_scheduling_time,
    step_name=args.build_event_step_name,
    step_number=args.build_event_step_number,
    result=args.build_event_result,
    extra_result_code=args.build_event_extra_result_code,
    timestamp_kind=args.event_mon_timestamp_kind,
    event_timestamp=args.event_mon_event_timestamp,
    goma_stats=goma_stats,
    goma_error=args.build_event_goma_error,
    goma_crash_report_id=goma_crash_report_id))


def send_events_from_file(args):
  """Entry point when --events-from-file is passed."""
  file_list = get_event_file_list(args.events_from_file)
  status = True

  LOGGER.info("Processing %d files", len(file_list))
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
      status = False

  return status


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
    events (iterable of event_mon.Event): events read from the file.
  """
  events = []
  with open(filename, 'r') as f:
    lineno = 0
    for line in f:
      lineno += 1
      if not line.strip():
        continue
      try:
        args = json.loads(line)
      except ValueError:
        LOGGER.error("Unparseable line in %s: %s", filename, line)
        continue

      if 'build-event-type' in args:
        events.append(
          event_mon.get_build_event(
            args.get('build-event-type'),
            args.get('build-event-hostname'),
            args.get('build-event-build-name'),
            build_number=args.get('build-event-build-number'),
            build_scheduling_time=args.get('build-event-build-scheduling-time'),
            step_name=args.get('build-event-step-name'),
            step_number=args.get('build-event-step-number'),
            result=args.get('build-event-result'),
            extra_result_code=args.get('build-event-extra-result-code'),
            timestamp_kind=args.get('event-mon-timestamp-kind'),
            event_timestamp=args.get('event-mon-event-timestamp'),
            service_name=args.get('event-mon-service-name')))
      else:
        LOGGER.warning('build-event-type field not found, skipping line '
                       '%d in %s', lineno, filename)
  return events
