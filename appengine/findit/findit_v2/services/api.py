# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This encapsulate the main Findit APIs for external requests."""

import logging

from google.protobuf.field_mask_pb2 import FieldMask

from common.waterfall import buildbucket_client

from findit_v2.services import projects
from findit_v2.services.context import Context
from findit_v2.services.detection import api as detection_api


def OnBuildCompletion(project, bucket, builder_name, build_id, build_result):
  """Processes the completed build.

  Returns:
    False if it is unsupported or skipped; otherwise True.
  """
  # Skip builders that are not in the whitelist of a supported project/bucket.
  supported_builders = projects.LUCI_PROJECTS.get(project, {}).get(bucket)
  if not supported_builders or builder_name not in supported_builders:
    return False

  assert bucket == 'ci', 'Only support ci bucket for %s, but got %s' % (project,
                                                                        bucket)

  # Skip builds that didn't fail.
  if build_result != 'FAILURE':
    logging.debug('Build %s/%s/%s/%s is not a failure', project, bucket,
                  builder_name, build_id)
    return False

  build = buildbucket_client.GetV2Build(build_id, fields=FieldMask(paths=['*']))

  if (build.input.gitiles_commit.host !=
      projects.GERRIT_PROJECTS[project]['gitiles-host'] or
      build.input.gitiles_commit.project !=
      projects.GERRIT_PROJECTS[project]['name']):
    logging.warning('Unexpected gitiles project for build: %r', build_id)
    return False

  context = Context(
      luci_project_name=project,
      gitiles_host=projects.GERRIT_PROJECTS[project]['gitiles-host'],
      gitiles_project=projects.GERRIT_PROJECTS[project]['name'],
      gitiles_ref=build.input.gitiles_commit.ref,
      gitiles_id=build.input.gitiles_commit.id)

  detection_api.OnBuildFailure(context, build)
  return True
