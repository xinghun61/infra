# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from datetime import datetime
import gzip
import io
import inspect
import logging
import json
import re
import urllib

from buildbucket_proto import common_pb2
from buildbucket_proto.build_pb2 import BuilderID
from google.protobuf import json_format
from google.protobuf.field_mask_pb2 import FieldMask

from common import rpc_util
from common.waterfall import buildbucket_client
from findit_v2.services.context import Context
from gae_libs.caches import PickledMemCache
from libs.cache_decorator import Cached
from services import git
from waterfall.build_info import BuildInfo

# TODO(crbug.com/787676): Use an api rather than parse urls to get the relevant
# data out of a build/tryjob url.
_HOST_NAME_PATTERN = (
    r'https?://(?:(?:build|ci)\.chromium\.org/p|\w+\.\w+\.google\.com/i)')

_MASTER_URL_PATTERN = re.compile(r'^%s/([^/]+)(?:/.*)?$' % _HOST_NAME_PATTERN)

_MILO_MASTER_URL_PATTERN = re.compile(
    r'^https?://luci-milo\.appspot\.com/buildbot/([^/]+)(?:/.*)?$')

_CI_MASTER_URL_PATTERN = re.compile(
    r'^https?://ci\.chromium\.org/buildbot/([^/]+)(?:/.*)?$')

_CI_LONG_MASTER_URL_PATTERN = re.compile(
    r'^https?://ci\.chromium\.org/p/chromium/([^/]+)(?:/.*)?$')

_MASTER_URL_PATTERNS = [  # yapf: disable
    _MASTER_URL_PATTERN,
    _MILO_MASTER_URL_PATTERN,
    _CI_MASTER_URL_PATTERN,
    _CI_LONG_MASTER_URL_PATTERN,
]

_MILO_SWARMING_TASK_URL_PATTERN = re.compile(
    r'^https?://luci-milo\.appspot\.com/swarming/task/([^/]+)(?:/.*)?$')

_BUILD_URL_PATTERN = re.compile(
    r'^%s/([^/]+)/builders/([^/]+)/builds/(\d+)(?:/.*)?$' % _HOST_NAME_PATTERN)

_MILO_BUILD_URL_PATTERN = re.compile(
    r'^https?://luci-milo\.appspot\.com/buildbot/([^/]+)/([^/]+)/(\d+)'
    '(?:/.*)?$')

_MILO_BUILD_LONG_URL_PATTERN = re.compile(
    r'^https?://luci-milo\.appspot\.com/p/([^/]+)/builders/([^/]+)/([^/]+)'
    '/(\d+)(?:/.*)?$')  # pylint: disable=anomalous-backslash-in-string

_CI_BUILD_URL_PATTERN = re.compile(
    r'^https?://ci\.chromium\.org/buildbot/([^/]+)/([^/]+)/(\d+)'
    '(?:/.*)?$')

_CI_BUILD_LONG_URL_PATTERN = re.compile(
    r'^https?://ci\.chromium\.org/p/([^/]+)/builders/([^/]+)/([^/]+)/(\d+)')

_BUILD_URL_PATTERNS = [  # yapf: disable
    _BUILD_URL_PATTERN,
    _MILO_BUILD_URL_PATTERN,
    _CI_BUILD_URL_PATTERN,
]

_MILO_ENDPOINT = 'https://luci-milo.appspot.com/prpc/milo.Buildbot'
_MILO_ENDPOINT_BUILD = '%s/GetBuildbotBuildJSON' % _MILO_ENDPOINT

_STEP_URL_PATTERN = re.compile(
    r'^%s/([^/]+)/builders/([^/]+)/builds/(\d+)/steps/([^/]+)(/.*)?$' %
    _HOST_NAME_PATTERN)

_COMMIT_POSITION_PATTERN = re.compile(r'refs/heads/master@{#(\d+)}$',
                                      re.IGNORECASE)

# These values are buildbot constants used for Build and BuildStep.
# This line was copied from buildbot/master/buildbot/status/results.py.
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, CANCELLED = range(7)


def _ProcessMiloData(response_json, master_name, builder_name,
                     build_number=''):  # pragma: no cover.
  if not response_json:
    return None
  try:
    response_data = json.loads(response_json)
  except Exception:  # pragma: no cover
    logging.error('Failed to load json data for %s-%s-%s' %
                  (master_name, builder_name, build_number))
    return None
  try:
    decoded_data = base64.b64decode(response_data.get('data'))
  except Exception:  # pragma: no cover
    logging.error('Failed to b64decode data for %s-%s-%s' %
                  (master_name, builder_name, build_number))
    return None

  if build_number:
    # Build data is not compressed.
    return decoded_data

  try:
    with io.BytesIO(decoded_data) as compressed_file:
      with gzip.GzipFile(fileobj=compressed_file) as decompressed_file:
        data_json = decompressed_file.read()
  except Exception:  # pragma: no cover
    logging.error('Failed to decompress data for %s-%s-%s' %
                  (master_name, builder_name, build_number))
    return None

  return data_json


def GetRecentCompletedBuilds(master_name, builder_name, page_size=None):
  """Returns a sorted list of recent completed builds for the given builder.

  Sorted by completed time, newer builds at beginning of the returned list.
  """
  luci_project, luci_bucket = GetLuciProjectAndBucketForMaster(master_name)
  search_builds_response = buildbucket_client.SearchV2BuildsOnBuilder(
      BuilderID(project=luci_project, bucket=luci_bucket, builder=builder_name),
      status=common_pb2.ENDED_MASK,
      page_size=page_size)

  return [build.number for build in search_builds_response.builds]


def GetMasterNameFromUrl(url):
  """Parses the given url and returns the master name."""
  if not url:
    return None

  match = None
  for pattern in _MASTER_URL_PATTERNS:
    match = pattern.match(url)
    if match:
      break
  if not match:
    return None
  return match.group(1)


def _ComputeCacheKeyForLuciBuilder(func, args, kwargs, namespace):
  """Returns a key for the Luci builder passed over to _GetBuildbotMasterName"""
  params = inspect.getcallargs(func, *args, **kwargs)
  return '%s-%s::%s::%s' % (namespace, params['project'], params['bucket_name'],
                            params['builder_name'])


# TODO(crbug/802940): Remove this when the API of getting LUCI build is ready.
@Cached(
    PickledMemCache(),
    namespace='luci-builder-to-master',
    key_generator=_ComputeCacheKeyForLuciBuilder)
def _GetBuildbotMasterName(project, bucket_name, builder_name, build_number):
  """Gets buildbot master name using builder_info and build_number."""
  build = buildbucket_client.GetV2BuildByBuilderAndBuildNumber(
      project, bucket_name, builder_name, build_number,
      FieldMask(paths=['input.properties.fields.mastername']))
  if not build:
    logging.error('Failed to get mastername for %s::%s::%s::%d', project,
                  bucket_name, builder_name, build_number)
    return None

  return build.input.properties['mastername']


# TODO(crbug/802940): Remove this when the API of getting LUCI build is ready.
def _ParseBuildLongUrl(url):
  """Parses _CI_BUILD_LONG_URL_PATTERN and _MILO_BUILD_LONG_URL_PATTERN urls."""
  match = None
  for pattern in (_CI_BUILD_LONG_URL_PATTERN, _MILO_BUILD_LONG_URL_PATTERN):
    match = pattern.match(url)
    if match:
      break
  if not match:
    return None

  project, bucket_name, builder_name, build_number = match.groups()
  # If the bucket_name is in the format of 'luci.chromium.ci', only uses 'ci'.
  bucket_name = bucket_name.split('.')[-1]
  builder_name = urllib.unquote(builder_name)

  master_name = _GetBuildbotMasterName(project, bucket_name, builder_name,
                                       int(build_number))
  if not master_name:
    return None

  return master_name, builder_name, int(build_number)


def ParseBuildUrl(url):
  """Parses the given build url.

  Return:
    (master_name, builder_name, build_number)
  """
  if not url:
    return None

  match = None
  for pattern in _BUILD_URL_PATTERNS:
    match = pattern.match(url)
    if match:
      break
  if not match:
    return _ParseBuildLongUrl(url)

  master_name, builder_name, build_number = match.groups()
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


def CreateBuildUrl(master_name, builder_name, build_number):
  """Creates the url for the given build."""
  builder_name = urllib.quote(builder_name)
  return 'https://ci.chromium.org/buildbot/%s/%s/%s' % (
      master_name, builder_name, build_number)


def GetBuildDataFromMilo(master_name, builder_name, build_number, http_client):
  """Returns the json-format data of the build."""
  data = {
      'master': master_name,
      'builder': builder_name,
      'buildNum': build_number,
      'exclude_deprecated': True,
  }
  status_code, response_json = rpc_util.DownloadJsonData(
      _MILO_ENDPOINT_BUILD, data, http_client)
  return status_code, _ProcessMiloData(response_json, master_name, builder_name,
                                       str(build_number))


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
  if not times or not times[0]:
    # For a build with infra failure, the start time might be set to None.
    return None
  return datetime.utcfromtimestamp(times[0])


def GetBuildEndTime(build_data_json):
  times = build_data_json.get('times')
  if not times or len(times) < 2 or not times[1]:
    return None
  return datetime.utcfromtimestamp(times[1])


def GetBuildResult(build_data_json):
  return build_data_json.get('results')


def GetCommitPosition(commit_position_line):
  if commit_position_line:
    match = _COMMIT_POSITION_PATTERN.match(commit_position_line)
    if match:
      return int(match.group(1))
  return None


def ExtractBuildInfo(master_name, builder_name, build_number, build_data):
  """Extracts and returns build information as an instance of BuildInfo."""
  build_info = BuildInfo(master_name, builder_name, build_number)
  data_json = json.loads(build_data)

  properties = data_json.get('properties') or []
  chromium_revision = GetBuildProperty(properties, 'got_revision')
  commit_position_line = GetBuildProperty(properties, 'got_revision_cp')
  parent_buildername = GetBuildProperty(properties, 'parent_buildername')
  parent_mastername = GetBuildProperty(properties, 'parent_mastername')
  runtime = GetBuildProperty(properties, '$recipe_engine/runtime') or {}
  buildbucket = GetBuildProperty(properties, 'buildbucket') or {}

  build_info.build_start_time = GetBuildStartTime(data_json)
  build_info.build_end_time = GetBuildEndTime(data_json)
  build_info.chromium_revision = chromium_revision
  build_info.commit_position = GetCommitPosition(commit_position_line)
  build_info.completed = data_json.get('currentStep') is None
  build_info.result = GetBuildResult(data_json)
  build_info.parent_buildername = parent_buildername
  build_info.parent_mastername = parent_mastername
  build_info.buildbucket_id = buildbucket.get('build', {}).get('id')
  build_info.buildbucket_bucket = buildbucket.get('build', {}).get('bucket')
  build_info.is_luci = runtime.get('is_luci')

  changes = (data_json.get('sourceStamp') or {}).get('changes') or []
  for change in changes:
    if (change.get('revision') and
        change['revision'] not in build_info.blame_list):
      build_info.blame_list.append(change['revision'])

  # Step categories:
  # 1. A step is passed if it is in SUCCESS or WARNINGS status.
  # 2. A step is failed if it is in FAILED status.
  # 3. A step is not passed if it is not in SUCCESS or WARNINGS status. This
  #    category includes steps in statuses: FAILED, SKIPPED, EXCEPTION, RETRY,
  #    CANCELLED, etc.
  steps = data_json.get('steps') or []
  for step_data in steps:
    step_name = step_data.get('name')

    if not step_name:
      continue

    if not step_data.get('isFinished'):
      # Skip steps that haven't started yet or are still running.
      continue

    step_result = GetStepResult(step_data)
    if step_result not in (SUCCESS, WARNINGS):
      build_info.not_passed_steps.append(step_name)

    if step_name == 'Failure reason':
      # 'Failure reason' is always red when the build breaks or has exception,
      # but it is not a failed step.
      continue

    step_logs = step_data.get('logs')
    if step_logs and step_logs[0][0] == 'preamble':
      # Skip a annotating step like "steps" or "slave_steps", which wraps other
      # steps. A failed annotated step like "content_browsertests" will make
      # the annotating step like "steps" fail too. Such annotating steps have a
      # log with name "preamble".
      continue

    if step_result in (SUCCESS, WARNINGS):
      build_info.passed_steps.append(step_name)
    elif step_result == FAILURE:
      build_info.failed_steps.append(step_name)

  return build_info


def GetBlameListForV2Build(build):
  """ Uses gitiles_commit from the previous build and current build to get
     blame_list.

  Args:
    build (build_pb2.Build): All info about the build.

  Returns:
    (list of str): Blame_list of the build.
  """
  search_build_response = buildbucket_client.SearchV2BuildsOnBuilder(
      build.builder, build_range=(None, build.id), page_size=1)
  previous_build = search_build_response.builds[
      0] if search_build_response.builds else None
  if not previous_build:
    logging.error('No previous build found for build %d.', build.id)
    return None

  context = Context(
      luci_project_name=build.builder.project,
      gitiles_host=build.input.gitiles_commit.host,
      gitiles_project=build.input.gitiles_commit.project,
      gitiles_ref=build.input.gitiles_commit.ref,
      gitiles_id=build.input.gitiles_commit.id)
  repo_url = git.GetRepoUrlFromContext(context)
  previous_build_gitiles_id = previous_build.input.gitiles_commit.id

  return git.GetCommitsBetweenRevisionsInOrder(previous_build_gitiles_id,
                                               context.gitiles_id, repo_url)


def ExtractBuildInfoFromV2Build(master_name, builder_name, build_number, build):
  """Generates BuildInfo using bb v2 build info.

  This conversion is needed to keep Findit v1 running, will be deprecated in
  v2 (TODO: crbug.com/966982).

  Args:
    master_name (str): The name of the master.
    builder_name (str): The name of the builder.
    build_number (int): The build number.
    build (build_pb2.Build): All info about the build.

  Returns:
    (BuildInfo)
  """
  build_info = BuildInfo(master_name, builder_name, build_number)

  input_properties = json_format.MessageToDict(build.input.properties)

  chromium_revision = build.input.gitiles_commit.id
  runtime = input_properties.get('$recipe_engine/runtime') or {}

  build_info.chromium_revision = chromium_revision
  context = Context(
      luci_project_name=build.builder.project,
      gitiles_host=build.input.gitiles_commit.host,
      gitiles_project=build.input.gitiles_commit.project,
      gitiles_ref=build.input.gitiles_commit.ref,
      gitiles_id=build.input.gitiles_commit.id)
  repo_url = git.GetRepoUrlFromContext(context)
  build_info.commit_position = git.GetCommitPositionFromRevision(
      context.gitiles_id, repo_url=repo_url)

  build_info.build_start_time = build.create_time.ToDatetime()
  build_info.build_end_time = build.end_time.ToDatetime()
  build_info.completed = bool(build_info.build_end_time)
  build_info.result = build.status
  build_info.parent_buildername = input_properties.get('parent_buildername')
  build_info.parent_mastername = input_properties.get('parent_mastername')
  build_info.buildbucket_id = build.id
  build_info.buildbucket_bucket = build.builder.bucket
  build_info.is_luci = runtime.get('is_luci')

  build_info.blame_list = GetBlameListForV2Build(build)

  # Step categories:
  # 1. A step is passed if it is in SUCCESS status.
  # 2. A step is failed if it is in FAILURE status.
  # 3. A step is not passed if it is not in SUCCESS status. This category
  #   includes steps in statuses: FAILURE, INFRA_FAILURE, CANCELED, etc.
  for step in build.steps:
    step_name = step.name
    step_status = step.status

    if not step_name:
      continue

    if step_status in [
        common_pb2.STATUS_UNSPECIFIED, common_pb2.SCHEDULED, common_pb2.STARTED
    ]:
      continue

    if step_status != common_pb2.SUCCESS:
      build_info.not_passed_steps.append(step_name)

    if step_name == 'Failure reason':
      # 'Failure reason' is always red when the build breaks or has exception,
      # but it is not a failed step.
      continue

    if not step.logs:
      # Skip wrapping steps.
      continue

    if step_status == common_pb2.SUCCESS:
      build_info.passed_steps.append(step_name)
    elif step_status == common_pb2.FAILURE:
      build_info.failed_steps.append(step_name)

  return build_info


def ValidateBuildUrl(url):
  return bool(
      _MILO_MASTER_URL_PATTERN.match(url) or
      _MILO_SWARMING_TASK_URL_PATTERN.match(url) or
      _BUILD_URL_PATTERN.match(url))


def GetLuciProjectAndBucketForMaster(master_name):
  """Matches master_name to Luci project and bucket.

  This is a temporary and hacky solution to remove Findit's dependencies on
  milo API.

  (TODO: crbug.com/965557): deprecate this when a long solution is in place.

  Args:
    master_name (str): Name of the master for this test.

  Returns:
    (str, str): Luci project and bucket
  """

  bucket = 'ci'
  if master_name.startswith('tryserver'):
    bucket = 'try'

  return 'chromium', bucket
