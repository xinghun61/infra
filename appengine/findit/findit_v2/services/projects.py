# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for the configuration of supported projects."""

import logging
import re

from findit_v2.services.chromeos_api import ChromeOSProjectAPI
from findit_v2.services.chromium_api import ChromiumProjectAPI
from findit_v2.services.failure_type import BuilderTypeEnum

# TODO (crbug.com/941625): Move these configs to a LUCI config.

# Supported projects by Findit. The names here are defined by Buildbucket.
# There is an assumption/requirement: supported builders and
# rerun_builders are separated.
# both supported_builders and rerun_builders can be none.
# {
#   'project-name': {
#     'buildbucket-bucket-name': {
#       # Findit does analyses on build failures of such builders.
#       'supported_builders': ['supported-builder-name'],
#       # Findit uses such builders to rerun builds during analyses.
#       'rerun_builders': ['bisect-builder-name'],
#       # Findit uses this to match builders that it needs to analyze.
#       'supported_builder_pattern': r'pattern',
#       # Findit uses this to match builders that it can use to rerun builds.
#       'rerun_builder_pattern': r'pattern',
#     }
#   }
# }
LUCI_PROJECTS = {
    'chromium': {
        'ci': {
            'supported_builders': ['Linux Builder']
        }
    },
    'chromeos': {
        'postsubmit': {
            'supported_builder_pattern': r'.*-postsubmit',
            'rerun_builder_pattern': r'.*-bisect',
            'supported_builders': ['postsubmit-orchestrator'],
            'rerun_builders': ['bisecting-orchestrator']
        }
    }
}

# Mapping from a Luci project name to its Gerrit/Gitiles project info.
GERRIT_PROJECTS = {
    'chromium': {
        'name': 'chromium/src',
        'gerrit-host': 'chromium-review.googlesource.com',
        'gitiles-host': 'chromium.googlesource.com',
        'dependencies': 'DEPS',
    },
    'chromeos': {
        'name': 'chromeos/manifest-internal',
        # No gerrit-host for chromeos project because now Findit only deals with
        # annealing snapshots commits and they don't have code review.
        'gitiles-host': 'chrome-internal.googlesource.com',
        'dependencies': 'placeholder/path/to/the/manifest.xml',
    }
}

# Project related configs.
PROJECT_CFG = {
    'chromium': {
        'project_api': ChromiumProjectAPI(),
        'should_group_failures': False,
    },
    'chromeos': {
        'project_api': ChromeOSProjectAPI(),
        'should_group_failures': True,
    }
}


def GetProjectAPI(project):
  """Gets the project API for the project."""
  project_api = PROJECT_CFG.get(project, {}).get('project_api')
  assert project_api, 'Unsupported project %s.' % project
  return project_api


def GetBuilderType(project, bucket, builder_name):
  # Skip builders that are not in the white list of a supported project/bucket.
  bucket_info = LUCI_PROJECTS.get(project, {}).get(bucket, {})
  if not bucket_info:
    logging.info(
        'project: %s, bucket: %s is not supported.' % (project, bucket))
    return BuilderTypeEnum.UNSUPPORTED

  def _is_builder_of_type(builder_type):
    if builder_name in bucket_info.get('{}_builders'.format(builder_type), []):
      return True

    builder_pattern = bucket_info.get('{}_builder_pattern'.format(builder_type))
    if builder_pattern and re.compile(builder_pattern).match(builder_name):
      return True
    return False

  for builder_type in [BuilderTypeEnum.SUPPORTED, BuilderTypeEnum.RERUN]:
    if _is_builder_of_type(builder_type.lower()):
      return builder_type
  return BuilderTypeEnum.UNSUPPORTED
