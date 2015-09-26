#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import hashlib
import httplib
import json
import logging
import os
import platform
import re
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib
import urllib2


# The path to the "infra/bootstrap/" directory.
BOOTSTRAP_DIR = os.path.dirname(os.path.abspath(__file__))
# The path to the "infra/" directory.
ROOT = os.path.dirname(BOOTSTRAP_DIR)
# The path where CIPD install lists are stored.
CIPD_LIST_DIR = os.path.join(BOOTSTRAP_DIR, 'cipd')
# Path to the CIPD bootstrap documentation repository.
CIPD_DOC_DIR = os.path.join(CIPD_LIST_DIR, 'doc')
# Default sysroot install root.
DEFAULT_INSTALL_ROOT = os.path.join(ROOT, 'cipd')

# Path to CA certs bundle file to use by default.
DEFAULT_CERT_FILE = os.path.join(ROOT, 'data', 'cacert.pem')

# Map of CIPD configuration based on the current architecture/platform. If a
# platform is not listed here, the bootstrap will be a no-op.
#
# This is keyed on the platform's (system, machine).
#
# It is ideal to use a raw `instance_id` as the version to avoid an unnecessary
# CIPD server round-trip lookup. This can be obtained for a given package via:
# $ cipd resolve \
#      infra/tools/cipd/ \
#     -version=git_revision:ed808139130f0ea8fd52fc64fd9ec47d150a2e49"
ARCH_CONFIG_MAP = {
  ('Linux', 'x86_64'): {
    'cipd_package': 'infra/tools/cipd/linux-amd64',
    'cipd_package_version': '99439270562c887c887b7538ed634ed3a3c0dc83',
    'cipd_install_list': 'cipd_linux_amd64.txt',
  },
}


def get_platform_config():
  key = (platform.system(), platform.machine())
  return key, ARCH_CONFIG_MAP.get(key)


def dump_json(obj):
  """Pretty-formats object to JSON."""
  return json.dumps(obj, indent=2, sort_keys=True, separators=(',',':'))


def ensure_directory(path):
  # Ensure the parent directory exists.
  if os.path.isdir(path):
    return
  if os.path.exists(path):
    raise ValueError("Target file's directory [%s] exists, but is not a "
                     "directory." % (path,))
  logging.debug('Creating directory: [%s]', path)
  os.makedirs(path)


def write_binary_file(path, data):
  """Writes a binary file to the disk."""
  ensure_directory(os.path.dirname(path))
  with open(path, 'wb') as fd:
    fd.write(data)


def write_tag_file(path, obj):
  with open(path, 'w') as fd:
    json.dump(obj, fd, sort_keys=True, indent=2)


def read_tag_file(path):
  try:
    with open(path, 'r') as fd:
      return json.load(fd)
  except (IOError, ValueError):
    return None


def execute(*cmd):
  if not logging.getLogger().isEnabledFor(logging.DEBUG):
    code = subprocess.call(cmd)
  else:
    # Execute the process, passing STDOUT/STDERR through our logger.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    for line in proc.stdout:
      logging.debug('%s: %s', cmd[0], line.rstrip())
    code = proc.wait()
  if code:
    logging.error('Process failed with exit code: %d', code)
  return code


class CipdError(Exception):
  """Raised by install_cipd_client on fatal error."""


class CipdBackend(object):
  """Properties and interaction with CIPD backend service."""

  # The default URL of the CIPD backend service.
  DEFAULT_URL = 'https://chrome-infra-packages.appspot.com'

  # Regular expression that matches CIPD raw instance IDs.
  _RE_INSTANCE_ID = re.compile(r'^[0-9a-f]{40}$')

  def __init__(self, url):
    self.url = url

  def call_api(self, endpoint, **query):
    """Sends GET request to CIPD backend, parses JSON response."""
    url = '%s/_ah/api/%s' % (self.url, endpoint)
    if query:
      url += '?' + urllib.urlencode(sorted(query.iteritems()), True)
    status, body = fetch_url(url)
    if status != 200:
      raise CipdError('Server replied with HTTP %d' % status)
    try:
      body = json.loads(body)
    except ValueError:
      raise CipdError('Server returned invalid JSON')
    status = body.get('status')
    if status != 'SUCCESS':
      m = body.get('error_message') or '<no error message>'
      raise CipdError('Server replied with error %s: %s' % (status, m))
    return body

  @classmethod
  def is_instance_id(cls, value):
    return cls._RE_INSTANCE_ID.match(value) is not None

  def resolve_instance_id(self, package, version):
    if self.is_instance_id(version):
      return version

    resp = self.call_api(
        'repo/v1/instance/resolve',
        package_name=package,
        version=version)
    return resp['instance_id']

  def get_client_info(self, package, instance_id):
    return self.call_api(
        'repo/v1/client',
        package_name=package,
        instance_id=instance_id)


class CipdClient(object):
  """Properties and interaction with CIPD client."""

  # Filename for the CIPD package/instance_id tag.
  _TAG_NAME = '.cipd_client_version'

  def __init__(self, cipd_backend, path):
    self.cipd_backend = cipd_backend
    self.path = path

  def exists(self):
    return os.path.isfile(self.path)

  def ensure(self, list_path, root):
    assert os.path.isfile(list_path)
    assert os.path.isdir(root)
    logging.debug('Installing CIPD packages from [%s] to [%s]', list_path, root)
    self.call(
        'ensure',
        '-list', list_path,
        '-root', root,
        '-service-url', self.cipd_backend.url)

  def call(self, *args):
    if execute(self.path, *args):
      raise CipdError('Failed to execute CIPD client: %s', ' '.join(args))

  def write_tag(self, package, instance_id):
    write_tag_file(self._cipd_tag_path, {
      'package': package,
      'instance_id': instance_id,
    })

  def read_tag(self):
    tag = read_tag_file(self._cipd_tag_path)
    if tag is None:
      return None, None
    return tag.get('package'), tag.get('instance_id')

  @property
  def _cipd_tag_path(self):
    return os.path.join(os.path.dirname(self.path), self._TAG_NAME)

  @classmethod
  def install(cls, cipd_backend, config, root):
    package = config['cipd_package']
    instance_id = cipd_backend.resolve_instance_id(
        package,
        config.get('cipd_package_version', 'latest'))
    logging.info('Installing CIPD client [%s] ID [%s]', package, instance_id)

    # Is this the version that's already installed?
    cipd_client = CipdClient(cipd_backend, os.path.join(root, 'cipd'))
    current = cipd_client.read_tag()
    if current == (package, instance_id) and os.path.isfile(cipd_client.path):
      logging.info('CIPD client already installed.')
      return cipd_client

    # Get the client binary URL.
    client_info = cipd_backend.get_client_info(package, instance_id)
    logging.info('CIPD client binary info:\n%s', dump_json(client_info))

    status, raw_client_data = fetch_url(
        client_info['client_binary']['fetch_url'])
    if status != 200:
      logging.error('Failed to fetch CIPD client binary (HTTP status %d)',
                    status)
      return None

    digest = hashlib.sha1(raw_client_data).hexdigest()
    if digest != client_info['client_binary']['sha1']:
      logging.error('CIPD client hash mismatch (%s != %s)', digest,
                    client_info['client_binary']['sha1'])
      return None

    write_binary_file(cipd_client.path, raw_client_data)
    os.chmod(cipd_client.path, 0755)
    cipd_client.write_tag(package, instance_id)
    return cipd_client



def fetch_url(url, headers=None):
  """Sends GET request (with retries).
  Args:
    url: URL to fetch.
    headers: dict with request headers.
  Returns:
    (200, reply body) on success.
    (HTTP code, None) on HTTP 401, 403, or 404 reply.
  Raises:
    Whatever urllib2 raises.
  """
  req = urllib2.Request(url)
  req.add_header('User-Agent', 'infra-install-cipd-packages')
  for k, v in (headers or {}).iteritems():
    req.add_header(str(k), str(v))
  i = 0
  while True:
    i += 1
    try:
      logging.debug('GET %s', url)
      return 200, urllib2.urlopen(req, timeout=60).read()
    except Exception as e:
      if isinstance(e, urllib2.HTTPError):
        logging.error('Failed to fetch %s, server returned HTTP %d', url,
                      e.code)
        if e.code in (401, 403, 404):
          return e.code, None
      else:
        logging.exception('Failed to fetch %s', url)
      if i == 20:
        raise
    logging.info('Retrying in %d sec.', i)
    time.sleep(i)


def setup_urllib2_ssl(cacert):
  """Configures urllib2 to validate SSL certs.
  See http://stackoverflow.com/a/14320202/3817699.
  """
  cacert = os.path.abspath(cacert)
  assert os.path.isfile(cacert)

  class ValidHTTPSConnection(httplib.HTTPConnection):
    default_port = httplib.HTTPS_PORT
    def __init__(self, *args, **kwargs):
      httplib.HTTPConnection.__init__(self, *args, **kwargs)
    def connect(self):
      sock = socket.create_connection(
          (self.host, self.port), self.timeout, self.source_address)
      if self._tunnel_host:
        self.sock = sock
        self._tunnel()
      self.sock = ssl.wrap_socket(
          sock, ca_certs=cacert, cert_reqs=ssl.CERT_REQUIRED)
  class ValidHTTPSHandler(urllib2.HTTPSHandler):
    def https_open(self, req):
      return self.do_open(ValidHTTPSConnection, req)
  urllib2.install_opener(urllib2.build_opener(ValidHTTPSHandler))


def main(argv):
  parser = argparse.ArgumentParser('Installs CIPD bootstrap packages.')
  parser.add_argument('-v', '--verbose', action='count', default=0,
      help='Increase logging verbosity. Can be specified multiple times.')
  parser.add_argument('--cipd-backend-url', metavar='URL',
      default=CipdBackend.DEFAULT_URL,
      help='Specify the CIPD backend URL (default is %(default)s)')
  parser.add_argument('-d', '--cipd-root-dir', metavar='PATH',
      default=DEFAULT_INSTALL_ROOT,
      help='Specify the root CIPD package installation directory.')
  parser.add_argument('--cacert', metavar='PATH', default=DEFAULT_CERT_FILE,
      help='Path to cacert.pem file with CA root certificates bundle (default '
           'is %(default)s)')

  opts = parser.parse_args(argv)

  # Setup logging verbosity.
  if opts.verbose == 0:
    level = logging.WARNING
  elif opts.verbose == 1:
    level = logging.INFO
  else:
    level = logging.DEBUG
  logging.getLogger().setLevel(level)

  # Configure `urllib2` to validate SSL certificates.
  logging.debug('CA certs bundle: %s', opts.cacert)
  setup_urllib2_ssl(opts.cacert)

  # Make sure our root directory exists.
  root = os.path.abspath(opts.cipd_root_dir)
  ensure_directory(root)

  platform_key, config = get_platform_config()
  if not config:
    logging.info('No bootstrap configuration for platform [%s].', platform_key)
    return 0

  cipd_backend = CipdBackend(opts.cipd_backend_url)
  cipd = CipdClient.install(cipd_backend, config, root)
  if not cipd:
    logging.error('Failed to install CIPD client.')
    return 1
  assert cipd.exists()

  # Install the CIPD list for this configuration.
  cipd_install_list = config.get('cipd_install_list')
  if cipd_install_list:
    cipd.ensure(os.path.join(CIPD_LIST_DIR, cipd_install_list), root)
  return 0


if __name__ == '__main__':
  logging.basicConfig()
  logging.getLogger().setLevel(logging.INFO)
  sys.exit(main(sys.argv[1:]))
