#!/usr/bin/python
# Copyright 2016 Google Inc. All Rights Reserved.
# pylint: disable=F0401

"""Cleanup directories on BuildBot master systems."""

import argparse
import bisect
import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
import time

from infra_libs import logs
from infra_libs.time_functions.parser import argparse_timedelta_type


LOGGER = logging.getLogger(__name__)


def _check_run(cmd, dry_run=True, cwd=None):
  if cwd is None:
    cwd = os.getcwd()

  if dry_run:
    LOGGER.info('(Dry run) Running command %s (cwd=%s)', cmd, cwd)
    return '', ''

  LOGGER.debug('Running command %s (cwd=%s)', cmd, cwd)
  proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=cwd)
  stdout, stderr = proc.communicate()

  rc = proc.returncode
  if rc != 0:
    LOGGER.error('Output for process %s (rc=%d, cwd=%s):\n'
                 'STDOUT:\n%s\nSTDERR:\n%s',
                 cmd, rc, cwd, stdout, stderr)
    raise subprocess.CalledProcessError(rc, cmd, None)
  return stdout, stderr


def parse_args(argv):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('master', nargs='+',
      help='Name of masters (*, master.*) to clean.')
  parser.add_argument('--max-twistd-log-age', metavar='AGE-TOKENS',
      default=None, type=argparse_timedelta_type,
      help='If set, "twistd.log" files older than this will be purged.')
  parser.add_argument('--production', action='store_true',
      help='If set, actually delete the files instead of listing them.')
  parser.add_argument('--gclient-root',
      help='The path to the directory containing the master checkout '
           '".gclient" file. If omitted, an attempt will be made to probe '
           'one.')

  logs.add_argparse_options(parser)

  opts = parser.parse_args(argv)
  logs.process_argparse_options(opts)
  return opts


def _process_master(opts, master_cfg):
  LOGGER.info('Cleaning up master: %s', master_cfg['mastername'])

  # Get a list of all files within the master directory.
  master_dir = master_cfg['master_dir']
  files, dirs = _list_untracked_files(master_dir)

  # Run a filter to identify all "builder" directories that are not currently
  # configured to the master.
  dirs = [x for x in dirs if (
      x not in master_cfg['builddirs'] and
      _is_builder_dir(os.path.join(master_dir, x)))]
  LOGGER.info('Identified %d superfluous build directories.', len(dirs))

  # Find old "twistd.log" files.
  old_twistd_logs = _find_old_twistd_logs(master_dir, files,
                                          opts.max_twistd_log_age)
  if len(old_twistd_logs) > 0:
    LOGGER.info('Identified %d old twistd.log files, starting with %s.',
                len(old_twistd_logs), old_twistd_logs[-1])

  for d in dirs:
    d = os.path.join(master_dir, d)
    LOGGER.info('Deleting superfluous directory: [%s]', d)
    if not opts.production:
      LOGGER.info('(Dry Run) Not deleting.')
      continue
    shutil.rmtree(d)

  for f in old_twistd_logs:
    f = os.path.join(master_dir, f)
    LOGGER.info('Removing old "twistd.log" file: [%s]', f)
    if not opts.production:
      LOGGER.info('(Dry Run) Not deleting.')
      continue
    os.remove(f)


def _find_old_twistd_logs(base, files, max_age):
  twistd_log_files = []
  if max_age is None:
    return twistd_log_files

  # Identify all "twistd.log" files to delete. We will do this by binary
  # searching the "twistd.log" space under the assumption that any log files
  # with higher generation than the specified file are older than files with
  # lower index.
  for f in files:
    gen = _parse_twistd_log_generation(f)
    if gen is not None:
      twistd_log_files.append((f, gen))
  twistd_log_files.sort(key=lambda x: x[1], reverse=True)

  threshold = datetime.datetime.now() - max_age
  lo, hi = 0, len(twistd_log_files)
  while lo < hi:
    mid = (lo+hi)//2
    path = os.path.join(base, twistd_log_files[mid][0])
    create_time = datetime.datetime.fromtimestamp(os.path.getctime(path))
    if create_time < threshold:
      hi = mid
    else:
      lo = mid+1
  return [x[0] for x in twistd_log_files[:lo]]


def _parse_twistd_log_generation(v):
  # Format is: "twistd.log[.###]"
  pieces = v.split('.')
  if len(pieces) != 3 or not (pieces[0] == 'twistd' and pieces[1] == 'log'):
    return None

  try:
    return int(pieces[2])
  except ValueError:
    return None


def _list_untracked_files(path):
  cmd = ['git', '-C', path, 'ls-files', '.', '--others', '--directory', '-z']
  stdout, _ = _check_run(cmd, dry_run=False)
  files, dirs = [], []

  def iter_null_terminated(data):
    while True:
      idx = data.find('\0')
      if idx < 0:
        yield data
        return
      v, data = data[:idx], data[idx+1:]
      yield v

  for name in iter_null_terminated(stdout):
    if name.endswith('/'):
      dirs.append(name.rstrip('/'))
    else:
      files.append(name)
  return files, dirs


def _is_builder_dir(dirname):
  return os.path.isfile(os.path.join(dirname, 'builder'))


def _load_master_cfg(gclient_root, master_dir):
  dump_master_cfg = os.path.join(gclient_root, 'build', 'scripts', 'tools',
                                 'dump_master_cfg.py')

  cmd = [sys.executable, dump_master_cfg, master_dir, '-']
  config, _ = _check_run(cmd, dry_run=False)
  config = json.loads(config)

  result = {
    'mastername': os.path.split(master_dir)[-1],
    'master_dir': master_dir,
    'builddirs': set(),
  }
  for bcfg in config.get('builders', ()):
    result['builddirs'].add(bcfg.get('builddir') or bcfg['name'])
  return result


def _find_master(gclient_root, mastername):
  if not mastername.startswith('master.'):
    mastername = 'master.' + mastername

  for candidate in (
      os.path.join(gclient_root, 'build', 'masters'),
      os.path.join(gclient_root, 'build_internal', 'masters'),
  ):
    candidate = os.path.join(candidate, mastername)
    if os.path.isdir(candidate):
      return candidate
  raise ValueError('Unable to locate master %s' % (mastername,))


def _find_gclient_root(opts):
  for candidate in (
      opts.gclient_root,
      os.path.join(os.path.expanduser('~'), 'buildbot'),
  ):
    if not candidate:
      continue
    candidate = os.path.abspath(candidate)
    if os.path.isfile(os.path.join(candidate, '.gclient')):
      return candidate
  raise Exception('Unable to find ".gclient" root.')


def _trim_prefix(v, prefix):
  if v.startswith(prefix):
    v = v[len(prefix)]
  return v


def _main(argv):
  opts = parse_args(argv)

  # Locate our gclient file root.
  gclient_root = _find_gclient_root(opts)

  # Dump the builders configured for each master.
  for master in sorted(set(opts.master)):
    LOGGER.info('Loading configuration for master "%s"...', master)
    master_dir = _find_master(gclient_root, master)
    master_cfg = _load_master_cfg(gclient_root, master_dir)
    _process_master(opts, master_cfg)

  return 0

if __name__ == '__main__':
  sys.exit(_main(sys.argv[1:]))
