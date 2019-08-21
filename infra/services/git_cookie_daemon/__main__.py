# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Runs a daemon to update git credentials from the GCE metadata server.

Only works inside a GCE with proper service accounts tagged.

Example invocation:
./run.py infra.services.git_cookie_daemon
"""
# This file is untested, keep as little code as possible in there.

import logging
import sys

from infra.services.git_cookie_daemon import git_cookie_daemon
from infra_libs import app


# https://chromium.googlesource.com/infra/infra/+/master/infra_libs/logs/README.md
LOGGER = logging.getLogger(__name__)


class GitCookieDaemon(app.BaseApplication):
  DESCRIPTION = sys.modules['__main__'].__doc__
  PROG_NAME = 'git_cookie_daemon'

  def add_argparse_options(self, parser):
    super(GitCookieDaemon, self).add_argparse_options(parser)

  def main(self, _opts):
    git_cookie_daemon.ensure_git_cookie_daemon()


if __name__ == '__main__':
  GitCookieDaemon().run()
