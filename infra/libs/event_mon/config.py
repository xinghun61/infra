# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
from infra.libs.event_mon.router import _Router
import socket

from infra.libs.event_mon.chrome_infra_log_pb2 import ChromeInfraEvent
from infra.libs.event_mon.chrome_infra_log_pb2 import ServiceEvent

_router = None

# Cache some generally useful values
cache = {}


def add_argparse_options(parser):
  # The default values should make sense for local testing, not production.
  parser.add_argument('--event-mon-dry-run', type=bool, default=True,
                      help='Whether events should be sent to the remote '
                      'server.')
  parser.add_argument('--event-mon-service-name',
                      help='Service name to use in log events.')
  parser.add_argument('--event-mon-hostname',
                      help='Hostname to use in log events.')
  parser.add_argument('--event-mon-appengine-name',
                      help='App name to use in log events.')

  # Provide information about version of code running.
  parser.add_argument('--event-mon-code-source-url',
                      help='URL where to get the source code (info sent in log '
                      'events.')
  parser.add_argument('--event-mon-code-dirty', type=bool,
                      help='Whether there are local modifications in the '
                      'currently running code (info sent in log events).')
  parser.add_argument('--event-mon-code-version',
                      help='Version string for the currently running code.')
  parser.add_argument('--event-mon-code-git-hash',
                      help='Git hash for the currently running code.')
  parser.add_argument('--event-mon-code-svn-revision', type=int,
                      help='Svn revision for the currently running code.')


def process_argparse_options(args):
  global _router
  if not _router:
    _router = _Router(dry_run=args.event_mon_dry_run)

    default_event = ChromeInfraEvent()

    if args.event_mon_hostname:
      default_event.event_source.host_name = args.event_mon_hostname
    else:
      hostname = socket.getfqdn()
      # hostname might be empty string or None on some systems, who knows.
      if hostname:  # pragma: no branch
        default_event.event_source.host_name = hostname

    if args.event_mon_service_name:
      default_event.event_source.service_name = args.event_mon_service_name
    if args.event_mon_appengine_name:
      default_event.event_source.appengine_name = args.event_mon_appengine_name

    # TODO(pgervais): set up code version
    cache['default_event'] = default_event


def close(timeout=5):
  """Make sure pending events are sent and gracefully shutdown.

  Call this right before exiting the program.

  Keyword Args:
    timeout (int): number of seconds to wait before giving up.
  Returns:
    success (bool): False if a timeout occured.
  """
  global _router
  success = True
  if _router:
    success = _router.close(timeout=timeout)
    _router = None
  return success
