# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Some constants used in Monorail hotlist pages."""

DEFAULT_COL_SPEC = 'Rank Project ID Stars Owner Summary Modified'
DEFAULT_RESULTS_PER_PAGE = 100
OTHER_BUILT_IN_COLS = ['Attachments', 'Stars', 'Opened', 'Closed', 'Modified',
                       'BlockedOn', 'Blocking', 'Blocked', 'MergedInto',
                       'Reporter', 'Cc', 'Project', 'Component',
                       'OwnerModified', 'StatusModified', 'ComponentModified']
# pylint: disable=line-too-long
ISSUE_INPUT_REGEX = "[a-z0-9][-a-z0-9]*[a-z0-9]:\d+(([,]|\s)+[a-z0-9][-a-z0-9]*[a-z0-9]:\d+)*"
