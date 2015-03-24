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


def add_argparse_options(parser):  # pragma: no cover
  # The default values should make sense for local testing, not production.
  parser.add_argument('--event-mon-run-type', default='dry',
                      choices=('dry', 'test', 'prod'),
                      help='Determine how to send data. "dry" does not send'
                      ' anything. "test" sends to the test endpoint, and '
                      '"prod" to the actual production endpoint.')
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


def process_argparse_options(args):  # pragma: no cover
  """Initializes event monitoring based on provided arguments.

  Args:
    args(argparse.Namespace): output of ArgumentParser.parse_args.
  """
  setup_monitoring(run_type=args.event_mon_run_type,
                   hostname=args.event_mon_hostname,
                   service_name=args.event_mon_service_name,
                   appengine_name=args.event_mon_appengine_name)


def setup_monitoring(run_type='dry',
                     hostname=None,
                     service_name=None,
                     appengine_name=None):
  """Initializes event monitoring.

  This function is mainly used to provide default global values which are
  required for the module to work.

  If you're implementing a command-line tool, use process_argparse_options
  instead.

  Args:
    run_type (str): One of 'dry', 'test', or 'prod'. Do respectively nothing,
      hit the testing endpoint and the production endpoint.
    hostname (str): hostname as it should appear in the event. If not provided
      a default value is computed.
    service_name (str): logical name of the service that emits events. e.g.
      "commit_queue".
    appengine_name (str): name of the appengine app, if running on appengine.
  """
  global _router
  if not _router:  # pragma: no cover
    ENDPOINTS = {
      'dry': None,
      'test': 'https://jmt17.google.com/log',
      'prod': 'https://play.googleapis.com/log',
      }
    # TODO(pgervais): log a warning if event_mon_run_type is invalid.
    endpoint = ENDPOINTS.get(run_type)
    _router = _Router(endpoint=endpoint)

    default_event = ChromeInfraEvent()

    hostname = hostname or socket.getfqdn()
    # hostname might be empty string or None on some systems, who knows.
    if hostname:  # pragma: no branch
      #TODO(pgervais): log when hostname is None or empty, because it's not
      # supposed to happen.
      default_event.event_source.host_name = hostname

    if service_name:
      default_event.event_source.service_name = service_name
    if appengine_name:
      default_event.event_source.appengine_name = appengine_name

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
