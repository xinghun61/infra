# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
from datetime import datetime
import gzip
import json
import re
import urllib

import cloudstorage as gcs

from waterfall.build_info import BuildInfo

_MASTER_URL_PATTERN = re.compile(r'^https?://build\.chromium\.org/p/([^/]+)'
                                  '(/.*)?$')

_BUILD_URL_PATTERN = re.compile(r'^https?://build\.chromium\.org/p/([^/]+)/'
                                 'builders/([^/]+)/builds/([\d]+)(/.*)?$')

_STEP_URL_PATTERN = re.compile(r'^https?://build\.chromium\.org/p/([^/]+)/'
                                 'builders/([^/]+)/builds/([\d]+)/steps/'
                                 '([^/]+)(/.*)?$')

# These values are buildbot constants used for Build and BuildStep.
# This line was copied from buildbot/master/buildbot/status/results.py.
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, CANCELLED = range(7)


def GetMasterNameFromUrl(url):
  """Parses the given url and returns the master name."""
  if not url:
    return None

  match = _MASTER_URL_PATTERN.match(url)
  if not match:
    return None
  return match.group(1)


def ParseBuildUrl(url):
  """Parses the given build url.

  Return:
    (master_name, builder_name, build_number)
  """
  if not url:
    return None

  match = _BUILD_URL_PATTERN.match(url)
  if not match:
    return None

  master_name, builder_name, build_number, _ = match.groups()
  builder_name = urllib.unquote(builder_name)
  return master_name, builder_name, int(build_number)


def ParseStepUrl(url):
  """Parses the given step url.

  Return:
    (master_name, builder_name, build_number, step_name)
  """
  if not url:
    return None

  match = _STEP_URL_PATTERN.match(url)
  if not match:
    return None

  master_name, builder_name, build_number, step_name, _ = match.groups()
  builder_name = urllib.unquote(builder_name)
  return master_name, builder_name, int(build_number), step_name


def CreateArchivedBuildUrl(master_name, builder_name, build_number):
  """Creates the url for the given build from archived build info."""
  builder_name = urllib.quote(builder_name)
  return ('https://chrome-build-extract.appspot.com/p/%s/builders/%s/builds/%s'
          '?json=1' % (master_name, builder_name, build_number))
        

def CreateBuildUrl(master_name, builder_name, build_number, json_api=False):
  """Creates the url for the given build."""
  builder_name = urllib.quote(builder_name)
  if json_api:
    return 'https://build.chromium.org/p/%s/json/builders/%s/builds/%s' % (
        master_name, builder_name, build_number)
  else:
    return 'https://build.chromium.org/p/%s/builders/%s/builds/%s' % (
        master_name, builder_name, build_number)


def CreateStdioLogUrl(master_name, builder_name, build_number, step_name):
  builder_name = urllib.quote(builder_name)
  step_name = urllib.quote(step_name)
  return ('https://build.chromium.org/p/%s/builders/%s/builds/%s/'
          'steps/%s/logs/stdio/text') % (
              master_name, builder_name, build_number, step_name)


def CreateGtestResultPath(master_name, builder_name, build_number, step_name):
  return ('/chrome-gtest-results/buildbot/%s/%s/%s/%s.json.gz') % (
              master_name, builder_name, build_number, step_name)


def GetBuildDataFromBuildMaster(master_name,
                                builder_name, build_number, http_client):
  """Returns the json-format data of the build from buildbot json API."""
  status_code, data = http_client.Get(
      CreateBuildUrl(master_name, builder_name, build_number, json_api=True))
  if status_code != 200:
    return None
  else:
    return data


def GetBuildDataFromArchive(master_name,
                            builder_name, build_number, http_client):
  """Returns the json-format data of the build from build archive."""
  status_code, data = http_client.Get(
      CreateArchivedBuildUrl(master_name, builder_name, build_number))
  if status_code != 200:
    return None
  else:
    return data


def GetStepStdio(master_name, builder_name, build_number,
                 step_name, http_client):
  """Returns the raw string of stdio of the specified step."""
  status_code, data = http_client.Get(
      CreateStdioLogUrl(master_name, builder_name, build_number, step_name))
  if status_code != 200:
    return None
  else:
    return data


def GetGtestResultLog(
    master_name, builder_name, build_number, step_name):  # pragma: no cover
  """Returns the content of the gtest json results for the gtest-based step."""
  try:
    archived_log_path = CreateGtestResultPath(
        master_name, builder_name, build_number, step_name)
    with contextlib.closing(gcs.open(archived_log_path)) as gtest_result_file:
      with gzip.GzipFile(fileobj=gtest_result_file) as unzipped_gtest_file:
        return unzipped_gtest_file.read()
  except gcs.NotFoundError:
    return None


def GetStepResult(step_data_json):
  """Returns the result of a step."""
  result = step_data_json.get('results')
  if result is None and step_data_json.get('isFinished'):
    # Without parameter filter=0 in the http request to the buildbot json api,
    # the value of the result of a passed step won't be present.
    return SUCCESS

  while isinstance(result, list):
    result = result[0]
  return result


def GetBuildProperty(properties, property_name):
  """Returns the property value from the given build properties."""
  for item in properties:
    if item[0] == property_name:
      return item[1]
  return None


def GetBuildStartTime(build_data_json):
  times = build_data_json.get('times')
  if not times:
    return None
  # TODO: convert to PST time?
  return datetime.fromtimestamp(times[0])


def GetBuildResult(build_data_json):
  return build_data_json.get('results')


def ExtractBuildInfo(master_name, builder_name, build_number, build_data):
  """Extracts and returns build information as an instance of BuildInfo."""
  build_info = BuildInfo(master_name, builder_name, build_number)

  data_json = json.loads(build_data)
  chromium_revision = GetBuildProperty(
      data_json.get('properties', []), 'got_revision')

  build_info.build_start_time = GetBuildStartTime(data_json)
  build_info.chromium_revision = chromium_revision
  build_info.completed = data_json.get('currentStep') is None
  build_info.result = GetBuildResult(data_json)

  changes = data_json.get('sourceStamp', {}).get('changes', [])
  for change in changes:
    build_info.blame_list.append(change['revision'])

  steps = data_json.get('steps', [])
  for step_data in steps:
    step_name = step_data['name']

    step_logs = step_data.get('logs')
    if step_logs and 'preamble' == step_logs[0][0]:
      # Skip a annotating step like "steps" or "slave_steps", which wraps other
      # steps. A failed annotated step like "content_browsertests" will make
      # the annotating step like "steps" fail too. Such annotating steps have a
      # log with name "preamble".
      continue

    if not step_data.get('isFinished', False):
      # Skip steps that haven't started yet or are still running.
      continue

    step_result = GetStepResult(step_data)
    if step_result in (SUCCESS, WARNINGS):
      build_info.passed_steps.append(step_name)
    elif step_result == FAILURE:
      build_info.failed_steps.append(step_name)

  return build_info
