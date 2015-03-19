# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import re
import sys
import infra.libs.event_mon as event_mon


def parse_revinfo(file_obj):
  """Parse the output of "gclient revinfo -a"

  Args:
    file_obj (File): file open for reading.

  Returns:
    revinfo (dict): <directory>: (URL, revision)
  """
  revision_expr = re.compile('(.*)@([^@]*)')

  revinfo = {}
  for line in file_obj:
    if ':' not in line:
      continue

    path, line = line.split(':', 1)
    if '@' in line:
      url, revision = revision_expr.match(line).groups()
      revision = revision.strip()
    else:
      # Split at the last @
      url, revision = line.strip(), None

    path = path.strip()
    url = url.strip()
    revinfo[path] = {'source_url': url, 'revision': revision}
  return revinfo


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

    Example:
    run.py infra.tool.send_monitoring_event --service-event-type=START \\
                                            --service-event-revinfo <filename>
    """, formatter_class=argparse.RawTextHelpFormatter)
  event_mon.add_argparse_options(parser)
  parser.add_argument('--service-event-type',
                      choices=('START', 'STOP', 'UPDATE', 'CURRENT_VERSION'),
                      default='START',
                      help='Kind of event to send.')
  parser.add_argument('--service-event-revinfo',
                      help='File to read revision information from, "-" means'
                      ' standard input. The file'
                      ' is supposed to contain the output of'
                      ' "gclient revinfo -a".')

  args = parser.parse_args(argv)
  return args


def main(argv):  # pragma: no cover
  args = get_arguments(argv)
  event_mon.process_argparse_options(args)

  revinfo = None
  if args.service_event_revinfo:
    if args.service_event_revinfo == '-':
      revinfo = parse_revinfo(sys.stdin)
    else:
      with open(args.service_event_revinfo, 'r') as f:
        revinfo = parse_revinfo(f)

  event_mon.send_service_event(args.service_event_type,
                               code_version=revinfo.values())
  event_mon.close()


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
