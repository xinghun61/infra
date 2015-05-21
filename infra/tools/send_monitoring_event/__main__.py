# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

import infra.libs.event_mon as event_mon
import infra_libs.logs

from infra.tools.send_monitoring_event import send_event


def main(argv):  # pragma: no cover
  # Does nothing when no arguments are passed, to make it safe to import this
  # module (main() is executed on import, because this file is called __main__).
  status = 0

  if len(argv) == 0:
    return status

  args = send_event.get_arguments(argv)

  event_mon.process_argparse_options(args)
  infra_libs.logs.process_argparse_options(args)

  if args.build_event_type:
    send_event.send_build_event(args)

  elif args.service_event_type:
    send_event.send_service_event(args)

  else:
    print >> sys.stderr, ('At least one of the --*-event-type options should '
                          'be provided. Nothing was sent.')
    status = 2
  event_mon.close()
  return status


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
