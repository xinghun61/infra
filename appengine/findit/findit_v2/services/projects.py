# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for the configuration of supported projects."""

from findit_v2.services.chromeos_api import ChromeOSProjectAPI
from findit_v2.services.chromium_api import ChromiumProjectAPI

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
#       'rerun_builders': ['bisect-builder-name']
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
            'supported_builders': ['arm-generic-postsubmit'],
            'rerun_builders': ['arm-generic-bisect']
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
        'group_failures': False,
    },
    'chromeos': {
        'project_api': ChromeOSProjectAPI(),
        'group_failures': True,
    }
}


def GetProjectAPI(project):
  """Gets the project API for the project."""
  return PROJECT_CFG.get(project, {}).get('project_api')
