# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is to process the code coverage metadata."""

import json
import logging
import zlib

from google.appengine.ext import ndb
from google.protobuf.field_mask_pb2 import FieldMask
from google.protobuf import json_format

from common.findit_http_client import FinditHttpClient
from common.waterfall.buildbucket_client import GetV2Build
from gae_libs.caches import PickledMemCache
from gae_libs.handlers.base_handler import BaseHandler, Permission
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.cache_decorator import Cached
from model.proto.gen.code_coverage_pb2 import CoverageReport
from model.code_coverage import CoverageData
from model.code_coverage import PostsubmitReport
from model.code_coverage import PresubmitReport
from waterfall import waterfall_config

# List of Gerrit projects that Findit supports.
_PROJECTS_WHITELIST = set(['chromium/src'])


def _GetValidatedData(gs_url):
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
  json_format.ParseDict(data, report, ignore_unknown_fields=True)
  del report  # Explicitly delete the proto message to release memory.
  logging.info('Finished validating coverage data.')

  return data


def _DecompressLines(line_ranges):
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


class ProcessCodeCoverageData(BaseHandler):  # pragma: no cover.
  PERMISSION_LEVEL = Permission.APP_SELF

  def _ProcessFullRepositoryData(self, commit, data, full_gs_dir, build_id):
    # Load the commit log first so that we could fail fast before redo all.
    repo_url = 'https://%s/%s' % (commit.host, commit.project)
    change_log = CachedGitilesRepository(FinditHttpClient(),
                                         repo_url).GetChangeLog(commit.id)
    assert change_log is not None, 'Failed to retrieve the commit log'

    # Save the file-level, directory-level and line-level coverage data.
    code_revision_index = '%s-%s' % (commit.project, commit.id)

    component_summaries = []
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
        logging.info('Dumped %d CoverageData entries of type %s', total,
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

      for dataset in data_iterator:
        for group_data in dataset:
          if actual_data_type == 'components':
            component_summaries.append({
                'name': group_data['path'],
                'summaries': group_data['summaries'],
            })

          coverage_data = CoverageData.Create(commit.host, code_revision_index,
                                              actual_data_type,
                                              group_data['path'], group_data)
          entities.append(coverage_data)
          entities, total = FlushEntries(entities, total, last=False)
        del dataset  # Explicitly release memory.
      FlushEntries(entities, total, last=True)

    if component_summaries:
      CoverageData.Create(commit.host, code_revision_index, actual_data_type,
                          '>>', {
                              'dirs': component_summaries,
                              'path': '>>'
                          }).put()

    # Create a repository-level record so that it shows up on UI.
    PostsubmitReport(
        key=ndb.Key(PostsubmitReport,
                    '%s$%s$%s' % (commit.host, commit.project, commit.id)),
        server_host=commit.host,
        project=commit.project,
        revision=commit.id,
        commit_position=change_log.commit_position,
        commit_timestamp=change_log.committer.time,
        summary_metrics=data.get('summaries'),
        gs_url='%s/index.html' % full_gs_dir,
        build_id=build_id).put()

  def _ProcessCLPatchData(self, patch, data, full_gs_dir, build_id):
    CoverageData.Create(patch.host, '%s-%s' % (patch.change, patch.patchset),
                        'patch', 'ALL', data).put()
    PresubmitReport(
        key=ndb.Key(
            PresubmitReport, '%s$%s$%s$%s' % (patch.host, patch.change,
                                              patch.patchset, build_id)),
        server_host=patch.host,
        project=patch.project,
        change=patch.change,
        patchset=patch.patchset,
        gs_url='%s/index.html' % full_gs_dir,
        build_id=build_id).put()

  def _processCodeCoverageData(self, build_id):
    print build_id

    build = GetV2Build(
        build_id,
        fields=FieldMask(paths=['id', 'output.properties', 'input', 'builder']))

    if not build:
      return BaseHandler.CreateError(
          'Could not retrieve build #%d from buildbucket, retry' % build_id,
          404)

    # Only process Chromium coverage bots.
    if (build.builder.project != 'chromium' or
        build.builder.bucket not in ('ci', 'try') or
        build.builder.builder not in ('linux-code-coverage',
                                      'linux-coverage-rel')):
      return

    # Convert the Struct to standard dict, to use .get, .iteritems etc.
    properties = dict(build.output.properties.items())
    gs_bucket = properties['coverage_gs_bucket']
    gs_path = properties['coverage_metadata_gs_path']

    # Ensure that the coverage data is ready.
    if not gs_bucket or not gs_path:
      logging.info('coverage GS bucket info not available in %r', build.id)
      return

    full_gs_dir = 'https://storage.googleapis.com/%s/%s' % (gs_bucket, gs_path)
    gs_url = '%s/all.json.gz' % full_gs_dir
    data = _GetValidatedData(gs_url)

    # Save the data in json.
    patches = build.input.gerrit_changes
    if patches:  # For a CL/patch, we save the entire data in one entity.
      patch = patches[0]  # Assume there is only 1 patch which is true in CQ.
      self._ProcessCLPatchData(patch, data['files'], full_gs_dir, build_id)
    else:  # For a commit, we save the data by file and directory.
      assert build.input.gitiles_commit is not None, 'Expect a commit'
      self._ProcessFullRepositoryData(build.input.gitiles_commit, data,
                                      full_gs_dir, build_id)

  def HandlePost(self):
    """Loads the data from GS bucket, and dumps them into ndb."""
    payload_json = json.loads(self.request.body)
    build_id = int(payload_json['build_id'])
    return self._processCodeCoverageData(build_id)

  def HandleGet(self):
    return self._processCodeCoverageData(int(self.request.get('build_id')))


def _IsServePresubmitCoverageDataEnabled():
  """Returns True if the feature to serve presubmit coverage data is enabled.

  Returns:
    Returns True if it is enabled, otherwise, False.
  """
  # Unless the flag is explicitly set, assuming disabled by default.
  return waterfall_config.GetCodeCoverageSettings().get(
      'serve_presubmit_coverage_data', False)


class ServeCodeCoverageData(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    host = self.request.get('host', 'chromium.googlesource.com')
    project = self.request.get('project', 'chromium/src')

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

      code_revision_index = '%s-%s' % (change, patchset)
      entity = CoverageData.Get(host, code_revision_index, 'patch', 'ALL')
      data = entity.data

      formatted_data = {'files': []}
      for file_data in data:
        formatted_data['files'].append({
            'path': file_data['path'],
            'lines': _DecompressLines(file_data['lines'])
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
      if not revision:
        query = PostsubmitReport.query(
            PostsubmitReport.server_host == host, PostsubmitReport.project ==
            project).order(-PostsubmitReport.commit_position).order(
                -PostsubmitReport.commit_timestamp)
        entities, _, _ = query.fetch_page(100)
        data = [e._to_dict() for e in entities]
      else:
        if data_type in ('dirs', 'files'):
          path = path or '//'
        elif data_type == 'components':
          path = path or '>>'
        assert data_type, 'Unknown data_type'

        code_revision_index = '%s-%s' % (project, revision)
        entity = CoverageData.Get(host, code_revision_index, data_type, path)
        data = entity.data if entity else None
      return {
          'data': {
              'host': host,
              'project': project,
              'revision': revision,
              'data_type': data_type,
              'path': path,
              'data': data,
          }
      }
    else:
      return BaseHandler.CreateError('Invalid request', 400)
