# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is to process the code coverage metadata."""

import collections
import json
import logging
import re
import urlparse
import zlib

import cloudstorage

from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.protobuf.field_mask_pb2 import FieldMask
from google.protobuf import json_format

from common import monitoring
from common.findit_http_client import FinditHttpClient
from common.waterfall.buildbucket_client import GetV2Build
from gae_libs.caches import PickledMemCache
from gae_libs.handlers.base_handler import BaseHandler, Permission
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.cache_decorator import Cached
from libs.deps import chrome_dependency_fetcher
from libs.time_util import ConvertUTCToPST
from model import entity_util
from model.proto.gen.code_coverage_pb2 import CoverageReport
from model.code_coverage import DependencyRepository
from model.code_coverage import PostsubmitReport
from model.code_coverage import FileCoverageData
from model.code_coverage import PresubmitCoverageData
from model.code_coverage import SummaryCoverageData
from waterfall import waterfall_config

# List of Gerrit projects that the Code Coverage service supports.
_PROJECTS_WHITELIST = set(['chromium/src'])
_ALLOWED_GITILES_HOST = set([
    'android.googlesource.com',
    'aomedia.googlesource.com',
    'boringssl.googlesource.com',
    'chromium.googlesource.com',
    'dawn.googlesource.com',
    'pdfium.googlesource.com',
    'quiche.googlesource.com',
    'skia.googlesource.com',
    'swiftshader.googlesource.com',
    'webrtc.googlesource.com',
])

# The regex to extract the build id from the url path.
_BUILD_ID_REGEX = re.compile(r'.*/build/(\d+)$')

# Cloud storage bucket used to store the source files fetched from gitile.
_SOURCE_FILE_GS_BUCKET = 'source-files-for-coverage'

# Dependencies to skip adding to manifest. Maps root repo url to list of
# dependency paths (relative to the root of the checkout).
_BLACKLISTED_DEPS = {
    'https://chromium.googlesource.com/chromium/src.git': [
        'src/ios/third_party/webkit/src'
    ],
}


def _GetValidatedData(gs_url):  # pragma: no cover.
  """Returns the json data from the given GS url after validation.

  Returns:
    json_data (dict): the json data of the file pointed by the given GS url, or
        None if the data can't be retrieved.
  """
  logging.info('Fetching %s', gs_url)
  status, content, _ = FinditHttpClient().Get(gs_url)
  assert status == 200, 'Can not retrieve the data: %s' % gs_url

  logging.info('Decompressing and loading coverage data...')
  decompressed_data = zlib.decompress(content)

  del content  # Explicitly release memory.
  data = json.loads(decompressed_data)
  del decompressed_data  # Explicitly release memory.
  logging.info('Finished decompressing and loading coverage data.')

  # Validate that the data is in good format.
  logging.info('Validating coverage data...')
  report = CoverageReport()
  json_format.ParseDict(data, report, ignore_unknown_fields=False)
  del report  # Explicitly delete the proto message to release memory.
  logging.info('Finished validating coverage data.')

  return data


def _DecompressLines(line_ranges):  # pragma: no cover.
  """Decompress the lines data to a flat format.

  For example:
  [
    {
      "count": 1,
      "first": 165, // inclusive
      "last": 166 // inclusive
    }
  ]

  After decompressing, it becomes:
  [
    {
      "line": 165,
      "count": 1
    },
    {
      "line": 166,
      "count": 1
    }
  ]

  Args:
    line_ranges: A list of dict, with format
                 [{"first": int, "last": int, "count": int}, ...], and note that
                 the [first, last] are both inclusive.

  Returns:
    A list of dict, with format
    [{"line": int, "count": int}].
  """
  decompressed_lines = []
  for line_range in line_ranges:
    for line_num in range(line_range['first'], line_range['last'] + 1):
      decompressed_lines.append({
          'line': line_num,
          'count': line_range['count']
      })

  return decompressed_lines


def _RetrieveManifest(repo_url, revision, os_platform):  # pragma: no cover.
  """Returns the manifest of all the dependencies for the given revision.

  Args:
    repo_url (str): The url to the Gitiles project of the root repository.
    revision (str): The revision of the root repository.
    os_platform (str): The platform of the code checkout.

  Returns:
    A list of DependencyRepository instances ordered reversely by the relative
    path of each dependency checkout in the checkout of the root repository.
    The longer the relative path, the smaller index in the returned list.

    The reverse order is to make it easy to reliably determine which dependency
    a file is from, when given a file path relative to the root repository.
  """
  manifest = []

  root_dir = 'src/'

  def AddDependencyToManifest(path, url, revision):  # pragma: no cover.
    if path.startswith(root_dir):
      path = path[len(root_dir):]
    assert not path.startswith('//')
    path = '//' + path
    if not path.endswith('/'):
      path = path + '/'

    # Parse the url to extract the hostname and project name.
    # For "https://chromium.google.com/chromium/src.git", we get
    # ParseResult(netloc='chromium.google.com', path='/chromium/src.git', ...)
    result = urlparse.urlparse(url)
    assert result.path, 'No project extracted from %s' % url

    manifest.append(
        DependencyRepository(
            path=path,
            server_host=result.netloc,
            project=result.path[1:],  # Strip the leading '/'.
            revision=revision))

  # Add the root repository.
  AddDependencyToManifest('src/', repo_url, revision)

  # Add all the dependent repositories.
  # DEPS fetcher now assumes chromium/src and master branch.
  dep_fetcher = chrome_dependency_fetcher.ChromeDependencyFetcher(
      CachedGitilesRepository.Factory(FinditHttpClient()))
  deps = dep_fetcher.GetDependency(revision, os_platform)
  for path, dep in deps.iteritems():
    # Remove clause when crbug.com/929315 gets fixed.
    if path in _BLACKLISTED_DEPS.get(repo_url, []):
      continue
    AddDependencyToManifest(path, dep.repo_url, dep.revision)

  manifest.sort(key=lambda x: len(x.path), reverse=True)
  return manifest


def _GetMatchedDependencyRepository(report, file_path):  # pragma: no cover.
  """Gets the matched dependency in the manifest of the report.

  Args:
    report (PostsubmitReport): The report that the file is associated with.
    file_path (str): Source absolute path to the file.

  Returns:
    A DependencyRepository if a matched one is found and it is whitelisted,
    otherwise None.
  """
  assert file_path.startswith('//'), 'All file path should start with "//".'

  dependency = None
  for dep in report.manifest:
    if file_path.startswith(dep.path):
      dependency = dep
      break

  if not dependency or dependency.server_host not in _ALLOWED_GITILES_HOST:
    return None

  return dependency


def _ComposeSourceFileGsPath(report, file_path, revision):
  """Composes a cloud storage path for a specific revision of a source file.

  Args:
    report (PostsubmitReport): The report that the file is associated with.
    file_path (str): Source absolute path to the file.
    revision (str): The gitile revision of the file in its own repo.

  Returns:
    Cloud storage path to the file, in the format /bucket/object. For example,
    /source-files-for-coverage/chromium.googlesource.com/v8/v8/src/date.cc/1234.
  """
  assert file_path.startswith('//'), 'All file path should start with "//".'
  assert revision, 'A valid revision is required'

  dependency = _GetMatchedDependencyRepository(report, file_path)
  assert dependency, (
      '%s file does not belong to any dependency repository' % file_path)

  # Calculate the relative path to the root of the dependency repository itself.
  relative_file_path = file_path[len(dependency.path):]
  return '/%s/%s/%s/%s/%s' % (_SOURCE_FILE_GS_BUCKET, dependency.server_host,
                              dependency.project, relative_file_path, revision)


def _IsFileAvailableInGs(gs_path):  # pragma: no cover.
  """Returns True if the specified object exists, otherwise False.

  Args:
    gs_path (str): Path to the file, in the format /bucket/object.

  Returns:
    True if the object exists, otherwise False.
  """
  try:
    _ = cloudstorage.stat(gs_path)
    return True
  except cloudstorage.NotFoundError:
    return False


def _GetFileContentFromGs(gs_path):  # pragma: no cover.
  """Reads the content of a file in cloud storage.

  This method is more expensive than |_IsFileAvailableInGs|, so if the goal is
  to check if a file exists, |_IsFileAvailableInGs| is preferred.

  Args:
    gs_path (str): Path to the file, in the format /bucket/object.

  Returns:
    The content of the file if it exists, otherwise None."""
  try:
    with cloudstorage.open(gs_path) as f:
      return f.read()
  except cloudstorage.NotFoundError:
    return None


def _WriteFileContentToGs(gs_path, content):  # pragma: no cover.
  """Writes the content of a file to cloud storage.

  Args:
    gs_path (str): Path to the file, in the format /bucket/object.
    content (str): Content of the file.
  """
  write_retry_params = cloudstorage.RetryParams(backoff_factor=2)
  with cloudstorage.open(
      gs_path, 'w', content_type='text/plain',
      retry_params=write_retry_params) as f:
    f.write(content)


def _GetFileContentFromGitiles(report, file_path,
                               revision):  # pragma: no cover.
  """Fetches the content of a specific revision of a file from gitiles.

  Args:
    report (PostsubmitReport): The report that the file is associated with.
    file_path (str): Source absolute path to the file.
    revision (str): The gitile revision of the file.

  Returns:
    The content of the source file."""
  assert file_path.startswith('//'), 'All file path should start with "//".'
  assert revision, 'A valid revision is required'

  dependency = _GetMatchedDependencyRepository(report, file_path)
  assert dependency, (
      '%s file does not belong to any dependency repository' % file_path)

  # Calculate the relative path to the root of the dependency repository itself.
  relative_file_path = file_path[len(dependency.path):]
  repo = CachedGitilesRepository(FinditHttpClient(), dependency.project_url)
  return repo.GetSource(relative_file_path, revision)


def _IsReportSuspicious(report):
  """Returns True if the newly generated report is suspicious to be incorrect.

  A report is determined to be suspicious if and only if the absolute difference
  between its line coverage percentage and the most recent visible report is
  greater than 1.00%.

  Args:
    report (PostsubmitReport): The report to be evaluated.

  Returns:
    True if the report is suspicious, otherwise False.
  """

  def _GetLineCoveragePercentage(report):
    line_coverage_percentage = None
    summary = report.summary_metrics
    for feature_summary in summary:
      if feature_summary['name'] == 'line':
        line_coverage_percentage = float(
            feature_summary['covered']) / feature_summary['total']
        break

    assert line_coverage_percentage is not None, (
        'Given report has invalid summary')
    return line_coverage_percentage

  target_server_host = report.gitiles_commit.server_host
  target_project = report.gitiles_commit.project
  most_recent_visible_reports = PostsubmitReport.query(
      PostsubmitReport.gitiles_commit.server_host == target_server_host,
      PostsubmitReport.gitiles_commit.project == target_project,
      PostsubmitReport.visible == True).order(
          -PostsubmitReport.commit_position).order(
              -PostsubmitReport.commit_timestamp).fetch(1)
  if not most_recent_visible_reports:
    logging.warn('No existing visible reports to use for reference, the new '
                 'report is determined as not suspicious by default')
    return False

  most_recent_visible_report = most_recent_visible_reports[0]
  if abs(
      _GetLineCoveragePercentage(report) -
      _GetLineCoveragePercentage(most_recent_visible_report)) > 0.01:
    return True

  return False


class FetchSourceFile(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandlePost(self):
    report_key = self.request.get('report_key')
    path = self.request.get('path')
    revision = self.request.get('revision')

    assert report_key, 'report_key is required'
    assert path, 'path is required'
    assert revision, 'revision is required'

    report = entity_util.GetEntityFromUrlsafeKey(report_key)
    assert report, (
        'Postsubmit report does not exist for urlsafe key' % report_key)

    file_content = _GetFileContentFromGitiles(report, path, revision)
    if not file_content:
      logging.error(
          'Failed to get file from gitiles for %s@%s' % (path, revision))
      return

    gs_path = _ComposeSourceFileGsPath(report, path, revision)
    _WriteFileContentToGs(gs_path, file_content)


class ProcessCodeCoverageData(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def _ProcessFullRepositoryData(self, commit, data, full_gs_dir, build_id):
    # Load the commit log first so that we could fail fast before redo all.
    repo_url = 'https://%s/%s.git' % (commit.host, commit.project)
    change_log = CachedGitilesRepository(FinditHttpClient(),
                                         repo_url).GetChangeLog(commit.id)
    assert change_log is not None, 'Failed to retrieve the commit log'

    # Load the manifest based on the DEPS file.
    # TODO(crbug.com/921714): output the manifest as a build output property.
    manifest = _RetrieveManifest(repo_url, commit.id, 'unix')

    report = PostsubmitReport.Create(
        server_host=commit.host,
        project=commit.project,
        ref=commit.ref,
        revision=commit.id,
        commit_position=change_log.commit_position,
        commit_timestamp=change_log.committer.time,
        manifest=manifest,
        summary_metrics=data.get('summaries'),
        build_id=build_id,
        visible=False)
    report.put()

    # Save the file-level, directory-level and line-level coverage data.
    for data_type in ('dirs', 'components', 'files', 'file_shards'):
      sub_data = data.get(data_type)
      if not sub_data:
        continue

      logging.info('Processing %d entries for %s', len(sub_data), data_type)

      actual_data_type = data_type
      if data_type == 'file_shards':
        actual_data_type = 'files'

      def FlushEntries(entries, total, last=False):
        # Flush the data in a batch and release memory.
        if len(entries) < 100 and not (last and entries):
          return entries, total

        ndb.put_multi(entries)
        total += len(entries)
        logging.info('Dumped %d coverage data entries of type %s', total,
                     actual_data_type)

        return [], total

      def IterateOverFileShards(file_shards):
        for file_path in file_shards:
          url = '%s/%s' % (full_gs_dir, file_path)
          # Download data one by one.
          yield _GetValidatedData(url).get('files', [])

      if data_type == 'file_shards':
        data_iterator = IterateOverFileShards(sub_data)
      else:
        data_iterator = [sub_data]

      entities = []
      total = 0

      component_summaries = []
      for dataset in data_iterator:
        for group_data in dataset:
          if actual_data_type == 'components':
            component_summaries.append({
                'name': group_data['path'],
                'path': group_data['path'],
                'summaries': group_data['summaries'],
            })

          if actual_data_type == 'files' and 'revision' in group_data:
            self._FetchAndSaveFileIfNecessary(report, group_data['path'],
                                              group_data['revision'])

          if actual_data_type == 'files':
            coverage_data = FileCoverageData.Create(
                server_host=commit.host,
                project=commit.project,
                ref=commit.ref,
                revision=commit.id,
                path=group_data['path'],
                data=group_data)
          else:
            coverage_data = SummaryCoverageData.Create(
                server_host=commit.host,
                project=commit.project,
                ref=commit.ref,
                revision=commit.id,
                data_type=actual_data_type,
                path=group_data['path'],
                data=group_data)

          entities.append(coverage_data)
          entities, total = FlushEntries(entities, total, last=False)
        del dataset  # Explicitly release memory.
      FlushEntries(entities, total, last=True)

      if component_summaries:
        component_summaries.sort(key=lambda x: x['path'])
        SummaryCoverageData.Create(
            server_host=commit.host,
            project=commit.project,
            ref=commit.ref,
            revision=commit.id,
            data_type='components',
            path='>>',
            data={
                'dirs': component_summaries,
                'path': '>>'
            }).put()
        component_summaries = []
        logging.info('Summary of all components are saved to datastore.')

    if not _IsReportSuspicious(report):
      report.visible = True
      report.put()
      monitoring.code_coverage_full_reports.increment({
          'host': commit.host,
          'project': commit.project,
          'ref': commit.ref or 'refs/heads/master',
      })

  def _FetchAndSaveFileIfNecessary(self, report, path, revision):
    """Fetches the file from gitiles and store to cloud storage if not exist.

    Args:
      report (PostsubmitReport): The report that the file is associated with.
      path (str): Source absolute path to the file.
      revision (str): The gitile revision of the file in its own repo.
    """
    assert path.startswith('//'), 'All file path should start with "//"'
    assert revision, 'A valid revision is required'

    gs_path = _ComposeSourceFileGsPath(report, path, revision)
    if _IsFileAvailableInGs(gs_path):
      return

    # Fetch the source files from gitile and save it in gs so that coverage
    # file view can be quickly rendered.
    url = ('/coverage/task/fetch-source-file')
    params = {
        'report_key': report.key.urlsafe(),
        'path': path,
        'revision': revision
    }
    taskqueue.add(
        method='POST',
        url=url,
        target='code-coverage-backend',
        queue_name='code-coverage-fetch-source-file',
        params=params)

  def _ProcessCLPatchData(self, patch, data, build_id):
    # For a CL/patch, we save the entire data in one entity.
    PresubmitCoverageData.Create(
        server_host=patch.host,
        change=patch.change,
        patchset=patch.patchset,
        build_id=build_id,
        data=data).put()

  def _processCodeCoverageData(self, build_id):
    build = GetV2Build(
        build_id,
        fields=FieldMask(paths=['id', 'output.properties', 'input', 'builder']))

    if not build:
      return BaseHandler.CreateError(
          'Could not retrieve build #%d from buildbucket, retry' % build_id,
          404)

    # Only process Chromium coverage bots.
    if (build.builder.project not in ('chromium', 'chrome') or
        build.builder.bucket not in ('coverage', 'ci', 'try') or
        build.builder.builder not in ('linux-code-coverage',
                                      'linux-coverage-rel')):
      return

    if build.builder.bucket == 'try':
      # Convert the Struct to standard dict, to use .get, .iteritems etc.
      properties = dict(build.output.properties.items())
      gs_bucket = properties.get('coverage_gs_bucket')
      gs_path = properties.get('coverage_metadata_gs_path')
      if properties.get('process_coverage_data_failure'):
        monitoring.code_coverage_cq_errors.increment({
            'project': build.builder.project,
            'bucket': build.builder.bucket,
            'builder': build.builder.builder,
        })
    else:
      # TODO(crbug.com/922104): There is an issue that when there are too many
      # test targets (350+ fuzzers), build output properties would exceed
      # maximum size and become empty in the response. Works it around
      # temporarily by hard coding the gs_bucket and gs_path, remove the hack
      # after the bug is fixed.
      gs_bucket = 'code-coverage-data'
      commit = build.input.gitiles_commit
      gs_path = ('postsubmit/%s/%s/%s/coverage/%s/%s/metadata') % (
          commit.host, commit.project, commit.id, build.builder.builder,
          build_id)

    # Ensure that the coverage data is ready.
    if not gs_bucket or not gs_path:
      logging.warn('coverage GS bucket info not available in %r', build.id)
      return

    full_gs_dir = 'https://storage.googleapis.com/%s/%s' % (gs_bucket, gs_path)
    gs_url = '%s/all.json.gz' % full_gs_dir

    data = _GetValidatedData(gs_url)

    # Save the data in json.
    if build.builder.bucket == 'try':
      # Assume there is only 1 patch which is true in CQ.
      assert len(build.input.gerrit_changes) == 1, 'Expect only one patchset'
      patch = build.input.gerrit_changes[0]
      self._ProcessCLPatchData(patch, data['files'], build_id)
    else:  # For a commit, we save the data by file and directory.
      assert build.input.gitiles_commit is not None, 'Expect a commit'
      self._ProcessFullRepositoryData(build.input.gitiles_commit, data,
                                      full_gs_dir, build_id)

  def HandlePost(self):
    """Loads the data from GS bucket, and dumps them into ndb."""
    logging.info('Processing: %s', self.request.path)
    match = _BUILD_ID_REGEX.match(self.request.path)
    if not match:
      logging.info('Build id not found')
      return

    build_id = int(match.group(1))
    return self._processCodeCoverageData(build_id)

  def HandleGet(self):
    return self.HandlePost()  # For local testing purpose.


def _IsServePresubmitCoverageDataEnabled():
  """Returns True if the feature to serve presubmit coverage data is enabled.

  Returns:
    Returns True if it is enabled, otherwise, False.
  """
  # Unless the flag is explicitly set, assuming disabled by default.
  return waterfall_config.GetCodeCoverageSettings().get(
      'serve_presubmit_coverage_data', False)


def _GetBanner(project):
  """If there is a service banner for a given project landing page, return it.

  E.g. a maintenance announcement or outage acknowledgement, etc.

  The setting is expected to be a dict mapping a project to the contents of the
  div tag for the banner. If no project banner is defined, return the default
  one.

  This expected to be None if no banner is to be shown.
  """
  banners = waterfall_config.GetCodeCoverageSettings().get(
      'project_banners', {})
  return banners.get(project, banners.get('default'))


def _GetPathRootAndSeparatorFromDataType(data_type):
  """Returns the path of the root and path separator for the given data type."""
  if data_type in ('files', 'dirs'):
    return '//', '/'
  elif data_type == 'components':
    return '>>', '>'
  return None, None


def _GetNameToPathSeparator(path, data_type):
  """Returns a list of [name, sub_path] for the given path.

  Example:
  1. //root/src/file.cc  -> [
       ['root/', '//root/'],
       ['src/', '//root/src/'],
       ['file.cc', '//root/src/file.cc']
     ]
  2. //root/src/path1/ -> [
       ['root/', '//root/'],
       ['src/', '//root/src/'],
       ['path1/', '//root/src/path1/']
     ]
  3. component1>component2  -> [
       ['component1', 'component1'],
       ['component2', 'component1>component2'],
     ]
  """
  path_parts = []
  if not path:
    return path_parts

  path_root, path_separator = _GetPathRootAndSeparatorFromDataType(data_type)
  if path == path_root:
    return path_parts

  if data_type == 'components':
    index = 0
  else:
    index = 2  # Skip the leading '//' in the path.

  while index >= 0:
    next_index = path.find(path_separator, index)
    if next_index >= 0:
      name = path[index:next_index + 1]
      if data_type == 'components':
        sub_path = path[:next_index]
      else:
        sub_path = path[:next_index + 1]
      next_index += 1
    else:
      name = path[index:]
      sub_path = path
    path_parts.append([name, sub_path])
    index = next_index

  return path_parts


class ServeCodeCoverageData(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    host = self.request.get('host', 'chromium.googlesource.com')
    project = self.request.get('project', 'chromium/src')
    ref = self.request.get('ref', 'refs/heads/master')

    change = self.request.get('change')
    patchset = self.request.get('patchset')

    revision = self.request.get('revision')
    path = self.request.get('path')
    data_type = self.request.get('data_type')

    if not data_type and path:
      if path.endswith('/'):
        data_type = 'dirs'
      elif path and '>' in path:
        data_type = 'components'
      else:
        data_type = 'files'

    logging.info('host=%s', host)
    logging.info('project=%s', project)
    logging.info('change=%s', change)
    logging.info('patchset=%s', patchset)
    logging.info('revision=%s', revision)
    logging.info('data_type=%s', data_type)
    logging.info('path=%s', path)

    if change and patchset:
      logging.info('Servicing coverage data for presubmit')
      if project not in _PROJECTS_WHITELIST:
        kwargs = {'is_project_supported': False}
        return BaseHandler.CreateError(
            error_message='Project "%s" is not supported.' % project,
            return_code=404,
            allowed_origin='*',
            **kwargs)

      if not _IsServePresubmitCoverageDataEnabled():
        # TODO(crbug.com/908609): Switch to 'is_service_enabled'.
        kwargs = {'is_project_supported': False}
        return BaseHandler.CreateError(
            error_message=('The functionality has been temporarity disabled.'),
            return_code=404,
            allowed_origin='*',
            **kwargs)

      entity = PresubmitCoverageData.Get(
          server_host=host, change=change, patchset=patchset)
      if not entity:
        return BaseHandler.CreateError(
            'Requested coverage data is not found.', 404, allowed_origin='*')

      data = entity.data
      formatted_data = {'files': []}
      for file_data in data:
        path = file_data['path']
        if path.startswith('//'):  # Check for safe. Old data don't have '//'.
          path = path[2:]
        formatted_data['files'].append({
            'path': path,
            'lines': _DecompressLines(file_data['lines']),
        })

      return {
          'data': {
              'host': host,
              'project': project,
              'change': change,
              'patchset': patchset,
              'data': formatted_data,
          },
          'allowed_origin': '*'
      }
    elif project:
      logging.info('Servicing coverage data for postsubmit')
      template = None

      if not revision:
        query = PostsubmitReport.query(
            PostsubmitReport.gitiles_commit.server_host == host,
            PostsubmitReport.gitiles_commit.project == project).order(
                -PostsubmitReport.commit_position).order(
                    -PostsubmitReport.commit_timestamp)
        entities, _, _ = query.fetch_page(100)

        # TODO(crbug.com/926237): Move the conversion to client side and use
        # local timezone.
        data = []
        for entity in entities:
          data.append({
              'gitiles_commit': {
                  'revision': entity.gitiles_commit.revision,
              },
              'commit_position': entity.commit_position,
              'commit_timestamp': ConvertUTCToPST(entity.commit_timestamp),
              'summary_metrics': entity.summary_metrics,
              'build_id': entity.build_id,
              'visible': entity.visible,
          })

        template = 'coverage/project_view.html'
        data_type = 'project'
      else:
        report = PostsubmitReport.Get(
            server_host=host, project=project, ref=ref, revision=revision)
        if not report:
          return BaseHandler.CreateError('Report record not found', 404)

        template = 'coverage/summary_view.html'
        if data_type == 'dirs':
          path = path or '//'
        elif data_type == 'components':
          path = path or '>>'
        else:
          if data_type != 'files':
            return BaseHandler.CreateError(
                'Expected data_type to be "files", but got "%s"' % data_type,
                400)

          template = 'coverage/file_view.html'

        if data_type == 'files':
          entity = FileCoverageData.Get(
              server_host=host,
              project=project,
              ref=ref,
              revision=revision,
              path=path)
        else:
          entity = SummaryCoverageData.Get(
              server_host=host,
              project=project,
              ref=ref,
              revision=revision,
              data_type=data_type,
              path=path)

        if not entity:
          return BaseHandler.CreateError('Requested path does not exist', 404)

        metadata = entity.data
        data = {
            'commit_position': report.commit_position,
            'metadata': metadata,
        }

        line_to_data = None
        if data_type == 'files':
          line_to_data = collections.defaultdict(dict)

          if 'revision' in metadata:
            gs_path = _ComposeSourceFileGsPath(report, path,
                                               metadata['revision'])
            file_content = _GetFileContentFromGs(gs_path)
            if not file_content:
              # Fetching files from Gitiles is slow, only use it as a backup.
              file_content = _GetFileContentFromGitiles(report, path,
                                                        metadata['revision'])
          else:
            # If metadata['revision'] is empty, it means that the file is not
            # a source file.
            file_content = None

          if not file_content:
            line_to_data[1]['line'] = '!!!!No source code available!!!!'
            line_to_data[1]['count'] = 0
          else:
            file_lines = file_content.splitlines()
            for i, line in enumerate(file_lines):
              # According to http://jinja.pocoo.org/docs/2.10/api/#unicode,
              # Jinja requires passing unicode objects or ASCII-only bytestring,
              # and given that it is possible for source files to have non-ASCII
              # chars, thus converting lines to unicode.
              line_to_data[i + 1]['line'] = unicode(line, 'utf8')
              line_to_data[i + 1]['count'] = -1

            for line in metadata['lines']:
              for i in range(line['first'], line['last'] + 1):
                line_to_data[i]['count'] = line['count']

          line_to_data = list(line_to_data.iteritems())
          line_to_data.sort(key=lambda x: x[0])
          data['line_to_data'] = line_to_data

      # Compute the mapping of the name->path mappings in order.
      path_parts = _GetNameToPathSeparator(path, data_type)
      path_root, _ = _GetPathRootAndSeparatorFromDataType(data_type)
      return {
          'data': {
              'host': host,
              'project': project,
              'ref': ref,
              'revision': revision,
              'path': path,
              'path_root': path_root,
              'data': data,
              'data_type': data_type,
              'path_parts': path_parts,
              'banner': _GetBanner(project),
          },
          'template': template,
      }
    else:
      return BaseHandler.CreateError('Invalid request', 400)
