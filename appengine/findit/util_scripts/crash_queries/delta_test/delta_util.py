# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Util functions for git repository processing for delta test."""

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

from gae_libs import appengine_util

# TODO(katesonia): move host to predator host after migration.
_FRACAS_FEEDBACK_URL_TEMPLATE = (
    'https://%s.appspot.com/crash/fracas-result-feedback?key=%s')
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
  # TODO: this has a race condition. Should ``try: os.makedirs`` instead,
  # discarding the error and returning if the directory already exists.
  if os.path.exists(directory):
    return

  os.makedirs(directory)


# TODO(crbug.com/662540): Add unittests.
def FlushResult(result, result_path, serializer=pickle):  # pragma: no cover
  print '\nFlushing results to', result_path
  EnsureDirExists(result_path)
  with open(result_path, 'wb') as f:
    serializer.dump(result, f)


# TODO(crbug.com/662540): Add unittests.
def PrintDelta(deltas, crash_num, app_id):  # pragma: no cover
  print ('\n+++++++++++++++++++++'
         '\nDelta on %d crashes '
         '\n+++++++++++++++++++++') % crash_num

  if not deltas:
    print 'Two sets of results are the same.'
    return

  for crash_id, delta in deltas.iteritems():
    print '\nCrash: %s\n%s\n' % (
        _FRACAS_FEEDBACK_URL_TEMPLATE % (app_id, crash_id), str(delta))


# TODO(crbug.com/662540): Add unittests.
def WriteDeltaToCSV(deltas, crash_num, app_id,
                    git_hash1, git_hash2, file_path):  # pragma: no cover
  EnsureDirExists(file_path)
  def _EncodeStr(string):
    return string.replace('\"', '\'') if string else ''

  with open(file_path, 'wb') as f:
    f.write('Delta between githash1 %s and githash2 %s on %d crashes\n\n' % (
        git_hash1, git_hash2, crash_num))
    f.write('crash url, project, components, cl 1, cl 2, regression_range\n')
    for crash_id, delta in deltas.iteritems():
      delta_dict_str = delta.delta_dict_str
      feedback_url = _FRACAS_FEEDBACK_URL_TEMPLATE % (app_id, crash_id)
      f.write('%s, "%s", "%s", "%s", "%s", "%s"\n' % (
          feedback_url,
          _EncodeStr(delta_dict_str.get('suspected_project', '')),
          _EncodeStr(delta_dict_str.get('suspected_components', '')),
          _EncodeStr(delta_dict_str.get('suspected_cl_1', '')),
          _EncodeStr(delta_dict_str.get('suspected_cl_2', '')),
          _EncodeStr(delta_dict_str.get('regression_range', ''))
      ))
