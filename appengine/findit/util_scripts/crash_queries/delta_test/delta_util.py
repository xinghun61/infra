# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Util functions for git repository processing."""

import base64
import hashlib
import json
import logging
import os
import pickle
import re
import subprocess
import traceback
import urllib2

import dev_appserver
dev_appserver.fix_sys_path()

from common import appengine_util

# TODO(katesonia): move host to azalea host after migration.
_FEEDBACK_URL_TEMPLATE = 'host/crash/fracas-result-feedback?key=%s'
GIT_HASH_PATTERN = re.compile(r'^[0-9a-fA-F]{40}$')


# TODO(crbug.com/662540): Add unittests.
def GenerateFileName(*args):  # pragma: no cover
  """Encodes args and returns the generated result file."""
  return hashlib.md5(pickle.dumps(args)).hexdigest()


# TODO(crbug.com/662540): Add unittests.
def IsGitHash(revision):  # pragma: no cover
  return GIT_HASH_PATTERN.match(str(revision)) or revision.lower() == 'master'


# TODO(crbug.com/662540): Add unittests.
def ParseGitHash(revision):  # pragma: no cover
  """Gets git hash of a revision."""
  if IsGitHash(revision):
    return revision

  try:
    # Can parse revision like 'HEAD', 'HEAD~3'.
    return subprocess.check_output(
        ['git', 'rev-parse', revision]).replace('\n', '')
  except: # pylint: disable=W
    logging.error('Failed to parse git hash for %s\nStacktrace:\n%s',
                  revision, traceback.format_exc())
    return None


# TODO(crbug.com/662540): Add unittests.
def EnsureDirExists(path):  # pragma: no cover
  directory = os.path.dirname(path)
  if os.path.exists(directory):
    return

  os.makedirs(directory)


# TODO(crbug.com/662540): Add unittests.
def FlushResult(result, result_path):  # pragma: no cover
  logging.info('\nFlushing results to %s', result_path)
  EnsureDirExists(result_path)
  with open(result_path, 'wb') as f:
    pickle.dump(result, f)


# TODO(crbug.com/662540): Add unittests.
def PrintDelta(deltas, crash_num):  # pragma: no cover
  logging.info(('\n+++++++++++++++++++++'
                '\nDelta on %d crashes '
                '\n+++++++++++++++++++++'), crash_num)

  if not deltas:
    logging.info('Two sets of results are the same.')
    return

  for crash_id, delta in deltas.iteritems():
    logging.info('\nCrash: %s\n%s\n',
                 _FEEDBACK_URL_TEMPLATE % crash_id,
                 str(delta))


# TODO(crbug.com/662540): Add unittests.
def WriteDeltaToCSV(deltas, crash_num,
                    git_hash1, git_hash2, file_path):  # pragma: no cover
  EnsureDirExists(file_path)
  def _EncodeStr(string):
    return string.replace('\"', '\'') if string else ''

  logging.info('Writing delta diff to %s\n', file_path)
  with open(file_path, 'wb') as f:
    f.write('Delta between githash1 %s and githash2 %s on %d crashes\n' % (
        git_hash1, git_hash2, crash_num))
    f.write('project, components, cls, regression_range\n')
    for crash_id, delta in deltas.iteritems():
      delta_str_dict = delta.delta_str_dict
      feedback_url = _FEEDBACK_URL_TEMPLATE % crash_id
      f.write('%s, "%s", "%s", "%s", "%s"\n' % (
          feedback_url,
          _EncodeStr(delta_str_dict.get('project', '')),
          _EncodeStr(delta_str_dict.get('components', '')),
          _EncodeStr(delta_str_dict.get('cls', '')),
          _EncodeStr(delta_str_dict.get('regression_range', ''))
      ))
