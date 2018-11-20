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

from gae_libs.handlers.base_handler import BaseHandler, Permission
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository

from common.findit_http_client import FinditHttpClient
from common.waterfall.buildbucket_client import GetV2Build
from model.proto.gen.code_coverage_pb2 import CoverageReport
from model.code_coverage import CoverageData
from model.code_coverage import PostsubmitReport
from model.code_coverage import PresubmitReport


class ProcessCodeCoverageData(BaseHandler):  # pragma: no cover.
  PERMISSION_LEVEL = Permission.APP_SELF

  def _ProcessFullRepositoryData(self, commit, data, gs_url, build_id):
    # Load the commit log first so that we could fail fast before redo all.
    repo_url = 'https://%s/%s' % (commit.host, commit.project)
    change_log = CachedGitilesRepository(FinditHttpClient(),
                                         repo_url).GetChangeLog(commit.id)
    assert change_log is not None, 'Failed to retrieve the commit log'

    # Save the file-level, directory-level and line-level coverage data.
    code_revision_index = '%s-%s' % (commit.project, commit.id)
    component_summaries = []
    repo_summaries = None
    for data_type in ('files', 'dirs', 'components'):
      if data_type not in data:
        continue

      entities = []
      sub_data = data[data_type] or []

      logging.info('Dumping %d entries for %s', len(sub_data), data_type)
      total = 0
      for group_data in sub_data:
        if data_type == 'components':
          component_summaries.append({
              'name': group_data['path'],
              'summaries': group_data['summaries'],
          })
        if data_type == 'dirs' and group_data['path'] == '//':
          repo_summaries = group_data['summaries']

        coverage_data = CoverageData.Create(commit.host, code_revision_index,
                                            data_type, group_data['path'],
                                            group_data)
        entities.append(coverage_data)
        if len(entities) >= 100:  # Batch save.
          total += len(entities)
          ndb.put_multi(entities)
          entities = []
          logging.info('Dumped %d CoverageData entities of type %s', total,
                       data_type)
      if entities:  # There might be some remaining data.
        ndb.put_multi(entities)
        total += len(entities)
        logging.info('Dumped %d CoverageData entities of type %s', total,
                     data_type)
      if component_summaries:
        CoverageData.Create(commit.host, code_revision_index, data_type, '>>', {
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
        summary_metrics=data.get('summaries', repo_summaries),
        gs_url=gs_url,
        build_id=build_id).put()

  def _ProcessCLPatchData(self, patch, data, gs_url, build_id):
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
        gs_url=gs_url,
        build_id=build_id).put()

  def _processCodeCoverageData(self, build_id):
    build = GetV2Build(
        build_id,
        fields=FieldMask(paths=['id', 'output.properties', 'input', 'builder']))

    if not build:
      return BaseHandler.CreateError(
          'Could not retrieve build #%d from buildbucket, retry' % build_id,
          404)

    # Convert the Struct to standard dict, to use .get, .iteritems etc.
    properties = dict(build.output.properties.items())
    gs_bucket = properties['coverage_gs_bucket']
    gs_path = properties['coverage_metadata_gs_path']

    gs_url = 'https://storage.googleapis.com/%s/%s/compressed.json.gz' % (
        gs_bucket, gs_path)
    status, content, _ = FinditHttpClient().Get(gs_url)
    if status != 200:
      return BaseHandler.CreateError(
          'Can not retrieve the coverage data: %s' % gs_url, 500)

    logging.info('Decompressing and loading coverage data...')
    decompressed_data = zlib.decompress(content)
    del content
    data = json.loads(decompressed_data)
    del decompressed_data
    logging.info('Finished decompressing and loading coverage data.')

    # Validate that the data is in good format.
    logging.info('Validating coverage data...')
    report = CoverageReport()
    json_format.ParseDict(data, report, ignore_unknown_fields=True)
    # Explicitly delete the proto message to release memory.
    del report
    logging.info('Finished validating coverage data...')

    # Save the data in json.
    patches = build.input.gerrit_changes
    if patches:  # For a CL/patch, we save the entire data in one entity.
      patch = patches[0]  # Assume there is only 1 patch which is true in CQ.
      self._ProcessCLPatchData(patch, data['files'], gs_url, build_id)
    else:  # For a commit, we save the data by file and directory.
      self._ProcessFullRepositoryData(build.input.gitiles_commit, data, gs_url,
                                      build_id)

  def HandlePost(self):
    """Loads the data from GS bucket, and dumps them into ndb."""
    payload_json = json.loads(self.request.body)
    build_id = int(payload_json['build_id'])
    return self._processCodeCoverageData(build_id)

  def HandleGet(self):
    return self._processCodeCoverageData(int(self.request.get('build_id')))


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

      code_revision_index = '%s-%s' % (change, patchset)
      entity = CoverageData.Get(host, code_revision_index, 'patch', 'ALL')
      data = entity.data  # TODO: change data format as needed.
      return {
          'data': {
              'host': host,
              'project': project,
              'change': change,
              'patchset': patchset,
              'data': data,
          },
          'allowed_origin': '*',
      }
    elif project:
      logging.info('Servicing coverage data for postsubmit')
      if not revision:
        logging.info('Repo-level data')
        query = PostsubmitReport.query(
            PostsubmitReport.server_host == host, PostsubmitReport.project ==
            project).order(-PostsubmitReport.commit_position).order(
                -PostsubmitReport.commit_timestamp)
        entities, _, _ = query.fetch_page(100)
        data = [e._to_dict() for e in entities]
      else:
        logging.info('Repo-level data')
        if data_type in ('dirs', 'files'):
          path = path or '//'
        elif data_type == 'components':
          path = path or '>>'

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
