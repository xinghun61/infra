# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import socket

from infra_libs.event_mon.chrome_infra_log_pb2 import ChromeInfraEvent
from infra_libs.event_mon.chrome_infra_log_pb2 import ServiceEvent
from infra_libs.event_mon.router import _Router
from infra_libs import authentication

DEFAULT_SERVICE_ACCOUNT_CREDS = 'service-account-event-mon.json'

# endpoint to hit for the various run types.
ENDPOINTS = {
  'dry': None,
  'test': 'https://jmt17.google.com/log',
  'prod': 'https://play.googleapis.com/log',
}

# Instance of router._Router (singleton)
_router = None

# Cache some generally useful values
cache = {}


def add_argparse_options(parser):  # pragma: no cover
  # The default values should make sense for local testing, not production.
  group = parser.add_argument_group('Event monitoring (event_mon) '
                                    'global options')
  group.add_argument('--event-mon-run-type', default='dry',
                      choices=('dry', 'test', 'prod'),
                      help='Determine how to send data. "dry" does not send\n'
                      'anything. "test" sends to the test endpoint, and \n'
                      '"prod" to the actual production endpoint.')
  group.add_argument('--event-mon-service-name',
                      help='Service name to use in log events.')
  group.add_argument('--event-mon-hostname',
                      help='Hostname to use in log events.')
  group.add_argument('--event-mon-appengine-name',
                      help='App name to use in log events.')
  group.add_argument('--event-mon-service-account-creds',
                     default=DEFAULT_SERVICE_ACCOUNT_CREDS,
                     metavar='JSON_FILE',
                     help="Path to a json file containing a service account's"
                     "\ncredentials. This is relative to the path specified\n"
                     "in --event-mon-service-accounts-creds-root\n"
                     "Defaults to '%(default)s'")
  group.add_argument('--event-mon-service-accounts-creds-root',
                     metavar='DIR',
                     default=authentication.SERVICE_ACCOUNTS_CREDS_ROOT,
                     help="Directory containing service accounts credentials.\n"
                     "Defaults to %(default)s"
                     )


def process_argparse_options(args):  # pragma: no cover
  """Initializes event monitoring based on provided arguments.

  Args:
    args(argparse.Namespace): output of ArgumentParser.parse_args.
  """
  setup_monitoring(
    run_type=args.event_mon_run_type,
    hostname=args.event_mon_hostname,
    service_name=args.event_mon_service_name,
    appengine_name=args.event_mon_appengine_name,
    service_account_creds=args.event_mon_service_account_creds,
    service_accounts_creds_root=args.event_mon_service_accounts_creds_root)


def setup_monitoring(run_type='dry',
                     hostname=None,
                     service_name=None,
                     appengine_name=None,
                     service_account_creds=None,
                     service_accounts_creds_root=None):
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

    service_account_creds (str): path to a json file containing a service
      account's credentials obtained from a Google Cloud project. **Path is
      relative to service_account_creds_root**, which is not the current path by
      default. See infra_libs.authentication for details.

    service_account_creds_root (str): path containing credentials files.

  """
  global _router
  logging.debug('event_mon: setting up monitoring.')

  if not _router:  # pragma: no cover
    default_event = ChromeInfraEvent()

    hostname = hostname or socket.getfqdn()
    # hostname might be empty string or None on some systems, who knows.
    if hostname:  # pragma: no branch
      default_event.event_source.host_name = hostname
    else:
      logging.warning('event_mon: unable to determine hostname.')

    if service_name:
      default_event.event_source.service_name = service_name
    if appengine_name:
      default_event.event_source.appengine_name = appengine_name

    cache['default_event'] = default_event
    cache['service_account_creds'] = service_account_creds
    cache['service_accounts_creds_root'] = service_accounts_creds_root

    if run_type not in ENDPOINTS:
      logging.error('Unknown run_type (%s). Setting to "dry"', run_type)
    endpoint = ENDPOINTS.get(run_type)
    _router = _Router(cache, endpoint=endpoint)


def close(timeout=5):
  """Make sure pending events are sent and gracefully shutdown.

  Call this right before exiting the program.

  Keyword Args:
    timeout (int): number of seconds to wait before giving up.
  Returns:
    success (bool): False if a timeout occured.
  """
  global _router, cache
  success = True
  if _router:
    success = _router.close(timeout=timeout)
    # If the thread is still alive, the global state can still change, thus
    # keep the values around for consistency.
    if success:  # pragma: no branch
      _router = None
      cache = {}
  return success
