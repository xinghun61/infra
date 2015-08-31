"""Handles reading and providing credentials for Gerrit.

This class supports reading credentials from both a '.netrc' file and a
'.gitcookies' file. It also provides methods for the default locations of these
files, and a method for getting an authentication tuple for a specific host name
(if it exists in one of the supported/specified credential files).
"""

import cookielib
import netrc
import os
import stat
import sys


class CredentialsException(Exception):
  """No valid credentials file is available."""


class NetrcException(CredentialsException):
  """Netrc file is missing or incorrect."""


class GitcookiesException(CredentialsException):
  """Gitcookies file is missing or incorrect."""


def get_default_netrc_path(): # pragma: no cover
  """Returns the default path of the '.netrc' file."""
  home_dir = os.path.expanduser('~')
  path = os.path.join(
      home_dir,
      '_netrc' if sys.platform.startswith('win') else '.netrc')
  return path

def get_default_gitcookies_path(): # pragma: no cover
  """Returns the default path of the '.gitcookies' file."""
  home_dir = os.path.expanduser('~')
  path = os.path.join(home_dir, '.gitcookies')
  return path

def get_default_credentials(): # pragma: no cover
  netrc_path = get_default_netrc_path()
  # Try to explictly load the netrc file. If it fails, we will pass None for the
  # netrc_path.
  try:
    load_netrc_file(netrc_path)
  except NetrcException:
    netrc_path = None
  # Try to explictly load the gitcookies file. If it fails, we will pass None
  # for the gitcookies_path.
  gitcookies_path = get_default_gitcookies_path()
  try:
    load_gitcookie_file(gitcookies_path)
  except GitcookiesException:
    gitcookies_path = None
  if not netrc_path and not gitcookies_path:
    raise CredentialsException('No default netrc or gitcookies file found')
  return Credentials(netrc_path, gitcookies_path)


class Credentials(object):
  """Handles extracting credentials for Gerrit from netrc or gitcookies.

  Args:
    netrc_path: Path to .netrc file
    gitcookies_path: Path to .gitcookies file
    auth: (login, token) tuple. Takes precedence for authentication.
  """
  def __init__(self, netrc_path=None, gitcookies_path=None, auth=None):
    if auth is not None:
      assert netrc_path is None and gitcookies_path is None
    self.auth = auth
    self.gitcookies = load_gitcookie_file(gitcookies_path)
    self.netrc = load_netrc_file(netrc_path) if netrc_path else None

  def __getitem__(self, host):
    """Returns the authentication tuple for the given host.

    Args:
      host: The host for which a matching auth tuple should be returned.

    Returns:
      (login, secret_token) tuple.

    Raises:
      KeyError: if no matching credentials were found.
    """
    if self.auth:
      return self.auth
    if self.netrc:
      auth = self.netrc.authenticators(host)
      # Get rid of the account in the tuple, it is always None, anyway.
      if auth:
        return (auth[0], auth[2])

    for domain, creds in self.gitcookies.iteritems():
      if cookielib.domain_match(host, domain):
        return creds
    raise KeyError


def load_gitcookie_file(path):
  """Loads .gitcookies file with gerrit credentials.

  Args:
    path: path to .gitcookies file.

  Returns:
    dict with domains as keys and (login, secret_token) as values.

  Raises:
    GitcookiesException: if the gitcookies file can't be read, for any reason.
  """
  gitcookies = {}
  if path is None:
    return gitcookies

  try:
    f = open(path, 'rb')
  except IOError as exc:
    raise GitcookiesException(
        'Could not read gitcookie file %s: %s' % (path, exc))

  with f:
    for line in f:
      try:
        fields = line.strip().split('\t')
        if line.strip().startswith('#') or len(fields) != 7:
          continue
        domain, xpath, key, value = fields[0], fields[2], fields[5], fields[6]
        if xpath == '/' and key == 'o':
          login, secret_token = value.split('=', 1)
          gitcookies[domain] = (login, secret_token)
      except (IndexError, ValueError, TypeError) as exc:
        raise GitcookiesException(
            'Cannot use gitcookies file %s due to a parsing error: %s' % (
                path, exc))
  return gitcookies

def load_netrc_file(path):
  """Loads netrc file with gerrit credentials.

  Args:
    path: path to .netrc file.

  Returns:
    netrc_obj (:class:`netrc.netrc`):

  Raises:
    NetrcException: if the netrc file can't be read, for any reason.
  """
  try:
    return netrc.netrc(path)
  except IOError as exc:
    raise NetrcException('Could not read netrc file %s: %s' % (path, exc))
  except netrc.NetrcParseError as exc: # pragma: no cover
    netrc_stat = os.stat(exc.filename)
    if netrc_stat.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
      raise NetrcException(
          'netrc file %s cannot be used because its file permissions '
          'are insecure.  netrc file permissions should be 600.' % path)
    else:
      raise NetrcException(
          'Cannot use netrc file %s due to a parsing error: %s' % (path, exc))
