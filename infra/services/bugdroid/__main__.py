# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import collections
import json
import os
import sys
import urlparse

from infra.libs import git2
from infra.libs.service_utils import outer_loop
from infra_libs import logs
from infra_libs import ts_mon
from infra.services.bugdroid import bugdroid


# TODO(sheyang): move to cloud
DIRBASE = os.path.splitext(os.path.basename(__file__))[0]
DATADIR = os.path.join(os.environ.get('HOME', ''), 'appdata', DIRBASE)
LOGDIR = os.path.join(DATADIR, 'logs')


def parse_args(args):  # pragma: no cover
  parser = argparse.ArgumentParser('./run.py %s' % __package__)
  parser.add_argument('-c', '--configfile',
                 help='Local JSON poller configuration file to override '
                      'confilg file from luci-config.')
  parser.add_argument('-d', '--credentials_db',
                 help='File to use for Codesite OAuth2 credentials storage.')
  parser.add_argument('--datadir', default=DATADIR,
                 help='Directory where persistent app data should be stored.')

  logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)
  outer_loop.add_argparse_options(parser)

  parser.set_defaults(
      ts_mon_target_type='task',
      ts_mon_task_service_name='bugdroid',
      ts_mon_task_job_name='bugdroid_job'
  )
  opts = parser.parse_args(args)

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  return opts, loop_opts


def main(args):  # pragma: no cover
  opts, loop_opts = parse_args(args)

  def outer_loop_iteration():
    return bugdroid.inner_loop(opts)

  loop_results = outer_loop.loop(
      task=outer_loop_iteration,
      sleep_timeout=lambda: 5.0,
      **loop_opts)

  return 0 if loop_results.success else 1


if __name__ == '__main__':  # pragma: no cover
  sys.exit(main(sys.argv[1:]))