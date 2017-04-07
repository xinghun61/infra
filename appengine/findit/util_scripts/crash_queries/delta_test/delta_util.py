# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Util functions for git repository processing for delta test."""

import base64
import hashlib
import logging
import os
import pickle
import re
import subprocess
import sys
import traceback
import urllib2

_SCRIPT_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           os.path.pardir)
sys.path.insert(1, _SCRIPT_DIR)
import script_util
script_util.SetUpSystemPaths()

from gae_libs import appengine_util

# TODO(katesonia): move host to predator host after migration.
_FEEDBACK_URL_TEMPLATE = (
    'https://%s.appspot.com/crash/%s-result-feedback?key=%s')
GIT_HASH_PATTERN = re.compile(r'^[0-9a-fA-F]{40}$')


def GenerateFileName(*args):  # pragma: no cover
  """Encodes args and returns the generated result file."""
  return hashlib.md5(pickle.dumps(args)).hexdigest()


def IsGitHash(revision):  # pragma: no cover
  return GIT_HASH_PATTERN.match(str(revision)) or revision.lower() == 'master'


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


def PrintDelta(deltas, crash_num, client_id, app_id):  # pragma: no cover
  """Prints delta in a pretty format for a list of deltas."""
  print ('\n+++++++++++++++++++++'
         '\nDelta on %d crashes '
         '\n+++++++++++++++++++++') % crash_num

  if not deltas:
    print 'Two sets of results are the same.'
    return

  for crash_id, delta in deltas.iteritems():
    print '\nCrash: %s\n%s\n' % (
        _FEEDBACK_URL_TEMPLATE % (app_id, client_id, crash_id), str(delta))


def _EncodeStrForCSV(string):  # pragma: no cover.
  """Encodes strings for printing in csv.

  In Excel/Google Sheet, to print newlines in CSV, '\n' has to be wrapped in
  double quotes.
  The problem with double quotes is, in Excel/Google sheet, to print a csv,
  if a string contains '\n', the string will be separated into several cells
  instead of one. For example:

  'a cat says:\n"one \n two\n three".' will be printed as below:
  ----------------------
  a cat says:
  ----------------------
  "one
  ----------------------
   two
  ----------------------
   three".
  ----------------------
  Only wrapping up it in double quotes, like this:
  ' "a cat says:\n'one\n two\n three'. " ', it can be printed as below:
  ----------------------
  a cat says:
  'one
   two
   three'.
  ----------------------
  But if we keep the double quotes inside of the original string, after wrapping
  it up in double quotes, it will be ' "a cat says:\n"one \ntwo \nthree". " ',
  it will be printed as below, because the "one\ntwo\nthree" is not in any
  double quotes.
  ----------------------
  a cat says:
  one
  ----------------------
  two
  ----------------------
  three.
  ----------------------
  """
  if not string:
    return ''

  string = str(string) if not isinstance(string, basestring) else string
  # Because the encoded string will be wrapped in double quotes, replace all
  # double quotes in string with single quotes.
  return string.replace('\"', '\'') if string else ''


def _PrettifySuspectClsForPrintInCSV(suspect_cls):  # pragma: no cover.
  suspect_cls_strs = []
  for index, suspect_cl in enumerate(suspect_cls):
    suspect_cls_strs.append(
        '(%d)\n%s\nScore: %.2f\nReason:\n%s\n' % (
            index + 1, suspect_cl.get('url'), suspect_cl.get('confidence'),
            suspect_cl.get('reasons')))

  return '\n'.join(suspect_cls_strs)


def _GetDeltaStringsForCSV(delta_dict):  # pragma: no cover.
  # The project delta.
  if 'suspected_project' in delta_dict:
    project1, project2 = delta_dict['suspected_project']
    projects = 'Project 1:\n%s\nProject 2:\n%s' % (project1 or '',
                                                   project2 or '')
  else:
    projects = ''

  # Supected cls delta.
  if 'suspected_cls' in delta_dict:
    suspect_cl_1, suspect_cl_2 = delta_dict['suspected_cls']
    suspect_cl_1 = _PrettifySuspectClsForPrintInCSV(suspect_cl_1 or [])
    suspect_cl_2 = _PrettifySuspectClsForPrintInCSV(suspect_cl_2 or [])
  else:
    suspect_cl_1 = ''
    suspect_cl_2 = ''

  # The components delta.
  if 'suspected_components' in delta_dict:
    components1, components2 = delta_dict['suspected_components']
    components = 'Components 1:\n%s\nComponents 2:\n%s' % (components1 or '',
                                                           components2 or '')
  else:
    components = ''

  # The regression range delta.
  if 'regression_range' in delta_dict:
    regression_range1, regression_range2 = delta_dict['regression_range']
    regression_ranges = (
        'Regression_range 1:\n%s\nRegression range 2:\n%s' % (
            regression_range1 or '', regression_range2 or ''))
  else:
    regression_ranges = ''

  return {'projects': _EncodeStrForCSV(projects),
          'suspect_cl_1': _EncodeStrForCSV(suspect_cl_1),
          'suspect_cl_2': _EncodeStrForCSV(suspect_cl_2),
          'components': _EncodeStrForCSV(components),
          'regression_ranges': _EncodeStrForCSV(regression_ranges)}


def WriteDeltaToCSV(deltas, crash_num, client_id, app_id,
                    git_hash1, git_hash2, file_path,
                    triage_results=None):  # pragma: no cover
  script_util.EnsureDirExists(file_path)
  triage_results = triage_results or {}
  with open(file_path, 'wb') as f:
    f.write('Delta between githash1 %s and githash2 %s on %d crashes\n\n' % (
        git_hash1, git_hash2, crash_num))
    f.write('crash url, project, cl 1, cl 2, culprit_cl, components, '
            'culprit_components, regression_range, culprit_regression_range\n')
    for crash_id, delta in deltas.iteritems():
      # The crash_url.
      feedback_url = _FEEDBACK_URL_TEMPLATE % (app_id, client_id, crash_id)
      deltas = _GetDeltaStringsForCSV(delta.delta_dict)

      triage_result = triage_results.get(crash_id)
      culprit_cl = '\n'.join(triage_result.get(
          'culprit_cls', [])) if triage_result else ''
      culprit_components = triage_result.get(
          'culprit_components', '') if triage_result else ''
      culprit_regression_range = triage_result.get(
          'culprit_regression_range', '') if triage_result else '',

      f.write('%s, "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s"\n' % (
          feedback_url, deltas['projects'], deltas['suspect_cl_1'],
          deltas['suspect_cl_2'], _EncodeStrForCSV(culprit_cl),
          deltas['components'], _EncodeStrForCSV(culprit_components),
          deltas['regression_ranges'],
          _EncodeStrForCSV(culprit_regression_range)))
