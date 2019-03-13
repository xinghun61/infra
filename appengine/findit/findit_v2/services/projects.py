# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for the configuration of supported projects."""

from findit_v2.services.chromium_api import ChromiumProjectAPI

# Supported projects by Findit. The names here are defined by Buildbucket.
# {
#   'project-name': {
#     'buildbucket-bucket-name': [
#       'supported-builder-name',
#     ]
#   }
# }
LUCI_PROJECTS = {
    'chromium': {
        'ci': ['Linux Builder'],
    },
    'chromeos': {
        'postsubmit': ['arm-generic-postsubmit'],
    }
}

# Mapping from a Luci project name to its Gerrit/Gitiles project info.
GERRIT_PROJECTS = {
    'chromium': {
        'name': 'chromium/src',
        'gerrit-host': 'chromium-review.googlesource.com',
        'gitiles-host': 'chromium.googlesource.com',
        'dependencies': 'DEPS',
        'project-api': ChromiumProjectAPI(),
    },
    'chromeos': {
        'dependencies': 'placeholder/path/to/the/manifest.xml',
    }
}
