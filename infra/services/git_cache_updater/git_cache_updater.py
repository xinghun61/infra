# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Git_cache_updater."""

import logging
import os
import requests
import subprocess
import sys
import cookielib


from infra_libs import utils
from infra.path_hacks.depot_tools import _depot_tools


GIT_CACHE_PY = os.path.join(_depot_tools, 'git_cache.py')


LOGGER = logging.getLogger(__name__)


class FailedToFetchProjectList(Exception):
  pass


def add_argparse_options(parser):
  """Define command-line arguments."""
  parser.add_argument(
      '--project', '-p', required=True,
      help='A GoogleSource.com address.  All repos under this project will be '
           'updated.')
  parser.add_argument(
      '--work-dir', '-w', default=os.getcwd(),
      help='Working directory to put cached files in, defaults to cwd.')


def update_bootstrap(repo, workdir):
  logging.info('Updating %s in %s' % (repo, workdir))
  env = os.environ.copy()
  env['CHROME_HEADLESS'] = '1'
  subprocess.call(
    [sys.executable, GIT_CACHE_PY,
     'update-bootstrap',
     '--cache-dir', workdir,
     '--no_bootstrap',
     repo],
    env=env)


def get_cookies():
  """Returns a cookielib.CookieJar object containing the git cookies."""
  cookie_file = subprocess.check_output(['git', 'config', 'http.cookiefile'])
  if not cookie_file:
    logging.info('Cookie file entry not found in gitconfig. Defaults to netrc.')
    return None
  else:
    logging.info('Found cookie file located at: %s' % cookie_file)
  with utils.temporary_directory() as tempdir:
    # Hack here because the gitcookie from googlesource doesn't contain the
    # magic netscape header that cookielib.MozillaCookieJar expects.
    temp_cookie_file = os.path.join(tempdir, 'cookies.txt')
    with open(temp_cookie_file, 'wb') as new_f:
      new_f.write(cookielib.MozillaCookieJar.header)
      with open(cookie_file.strip(), 'rb') as orig_f:
        new_f.write(orig_f.read())
    cookies = cookielib.MozillaCookieJar(temp_cookie_file)
    cookies.load()
    return cookies


def get_project_list(project):
  """Fetch the list of all git repositories in a project."""
  cookies = get_cookies()
  r = requests.get('%s?format=TEXT' % project, cookies=cookies)
  if r.status_code == 403:
    raise FailedToFetchProjectList('Auth failed, check your git credentials.')
  return ['%s%s' % (project, repo) for repo in r.text.splitlines()
          if repo and repo.lower() not in ['all-projects', 'all-users']]


def run(project, workdir):
  if not os.path.isdir(workdir):
    logging.debug('%s not found, creating...' % workdir)
    os.makedirs(workdir)
  # Run this serially for each project.  Running it overly parallel could cause
  # memory/harddrive exhaustion.
  for url in get_project_list(project):
    update_bootstrap(url, workdir)
