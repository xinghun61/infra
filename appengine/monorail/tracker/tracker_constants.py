# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Some constants used in Monorail issue tracker pages."""

import re

from proto import user_pb2


# Default columns shown on issue list page, and other built-in cols.
DEFAULT_COL_SPEC = 'ID Type Status Priority Milestone Owner Summary'
OTHER_BUILT_IN_COLS = [
    'AllLabels', 'Attachments', 'Stars', 'Opened', 'Closed', 'Modified',
    'BlockedOn', 'Blocking', 'Blocked', 'MergedInto',
    'Reporter', 'Cc', 'Project', 'Component',
    'OwnerModified', 'StatusModified', 'ComponentModified',
    'OwnerLastVisit']

# These are label prefixes that would conflict with built-in column names.
# E.g., no issue should have a *label* id-1234 or status-foo because any
# search for "id:1234" or "status:foo" would not look at labels.
RESERVED_PREFIXES = [
    'id', 'project', 'reporter', 'summary', 'status', 'owner', 'cc',
    'attachments', 'attachment', 'component', 'opened', 'closed',
    'modified', 'is', 'has', 'blockedon', 'blocking', 'blocked', 'mergedinto',
    'stars', 'starredby', 'description', 'comment', 'commentby', 'label',
    'hotlist', 'rank', 'explicit_status', 'derived_status', 'explicit_owner',
    'derived_owner', 'explicit_cc', 'derived_cc', 'explicit_label',
    'derived_label', 'last_comment_by', 'exact_component',
    'explicit_component', 'derived_component', 'alllabels']

# The columns are useless in the grid view, so don't offer them.
NOT_USED_IN_GRID_AXES = [
    'Summary', 'ID', 'Opened', 'Closed', 'Modified',
    'OwnerModified', 'StatusModified', 'ComponentModified',
    'OwnerLastVisit', 'AllLabels']

# Issues per page in the issue list
DEFAULT_RESULTS_PER_PAGE = 100

# Search field input indicating that the user wants to
# jump to the specified issue.
JUMP_RE = re.compile(r'^\d+$')

# Regular expression defining a single search term.
# Used when parsing the contents of the issue search field.
TERM_RE = re.compile(r'[-a-zA-Z0-9._]+')

# Regular expression used to validate new component leaf names.
# This should never match any string with a ">" in it.
COMPONENT_NAME_RE = re.compile(r'^[a-zA-Z]([-_]?[a-zA-Z0-9])+$')

# Regular expression used to validate new field names.
FIELD_NAME_RE = re.compile(r'^[a-zA-Z]([-_]?[a-zA-Z0-9])*$')

# The next few items are specifications of the defaults for project
# issue configurations.  These are used for projects that do not have
# their own config.
DEFAULT_CANNED_QUERIES = [
    # Query ID, Name, Base query ID (not used for built-in queries), conditions
    (1, 'All issues', 0, ''),
    (2, 'Open issues', 0, 'is:open'),
    (3, 'Open and owned by me', 0, 'is:open owner:me'),
    (4, 'Open and reported by me', 0, 'is:open reporter:me'),
    (5, 'Open and starred by me', 0, 'is:open is:starred'),
    (6, 'New issues', 0, 'status:new'),
    (7, 'Issues to verify', 0, 'status=fixed,done'),
    (8, 'Open with comment by me', 0, 'is:open commentby:me'),
    ]

DEFAULT_CANNED_QUERY_CONDS = {
    query_id: cond
    for (query_id, _name, _base, cond) in DEFAULT_CANNED_QUERIES}

ALL_ISSUES_CAN = 1
OPEN_ISSUES_CAN = 2

# Define well-known issue statuses.  Each status has 3 parts: a name, a
# description, and True if the status means that an issue should be
# considered to be open or False if it should be considered closed.
DEFAULT_WELL_KNOWN_STATUSES = [
    # Name, docstring, means_open, deprecated
    ('New', 'Issue has not had initial review yet', True, False),
    ('Accepted', 'Problem reproduced / Need acknowledged', True, False),
    ('Started', 'Work on this issue has begun', True, False),
    ('Fixed', 'Developer made source code changes, QA should verify', False,
     False),
    ('Verified', 'QA has verified that the fix worked', False, False),
    ('Invalid', 'This was not a valid issue report', False, False),
    ('Duplicate', 'This report duplicates an existing issue', False, False),
    ('WontFix', 'We decided to not take action on this issue', False, False),
    ('Done', 'The requested non-coding task was completed', False, False),
    ]

DEFAULT_WELL_KNOWN_LABELS = [
    # Name, docstring, deprecated
    ('Type-Defect', 'Report of a software defect', False),
    ('Type-Enhancement', 'Request for enhancement', False),
    ('Type-Task', 'Work item that doesn\'t change the code or docs', False),
    ('Type-Other', 'Some other kind of issue', False),
    ('Priority-Critical', 'Must resolve in the specified milestone', False),
    ('Priority-High', 'Strongly want to resolve in the specified milestone',
        False),
    ('Priority-Medium', 'Normal priority', False),
    ('Priority-Low', 'Might slip to later milestone', False),
    ('OpSys-All', 'Affects all operating systems', False),
    ('OpSys-Windows', 'Affects Windows users', False),
    ('OpSys-Linux', 'Affects Linux users', False),
    ('OpSys-OSX', 'Affects Mac OS X users', False),
    ('Milestone-Release1.0', 'All essential functionality working', False),
    ('Security', 'Security risk to users', False),
    ('Performance', 'Performance issue', False),
    ('Usability', 'Affects program usability', False),
    ('Maintainability', 'Hinders future changes', False),
    ]

# Exclusive label prefixes are ones that can only be used once per issue.
# For example, an issue would normally have only one Priority-* label, whereas
# an issue might have many OpSys-* labels.
DEFAULT_EXCL_LABEL_PREFIXES = ['Type', 'Priority', 'Milestone']

DEFAULT_USER_DEFECT_REPORT_TEMPLATE = {
    'name': 'Defect report from user',
    'summary': 'Enter one-line summary',
    'summary_must_be_edited': True,
    'content': (
        'What steps will reproduce the problem?\n'
        '1. \n'
        '2. \n'
        '3. \n'
        '\n'
        'What is the expected output?\n'
        '\n'
        '\n'
        'What do you see instead?\n'
        '\n'
        '\n'
        'What version of the product are you using? '
        'On what operating system?\n'
        '\n'
        '\n'
        'Please provide any additional information below.\n'),
    'status': 'New',
    'labels': ['Type-Defect', 'Priority-Medium'],
    }

DEFAULT_DEVELOPER_DEFECT_REPORT_TEMPLATE = {
    'name': 'Defect report from developer',
    'summary': 'Enter one-line summary',
    'summary_must_be_edited': True,
    'content': (
        'What steps will reproduce the problem?\n'
        '1. \n'
        '2. \n'
        '3. \n'
        '\n'
        'What is the expected output?\n'
        '\n'
        '\n'
        'What do you see instead?\n'
        '\n'
        '\n'
        'Please use labels and text to provide additional information.\n'),
    'status': 'Accepted',
    'labels': ['Type-Defect', 'Priority-Medium'],
    'members_only': True,
    }


DEFAULT_TEMPLATES = [
    DEFAULT_DEVELOPER_DEFECT_REPORT_TEMPLATE,
    DEFAULT_USER_DEFECT_REPORT_TEMPLATE,
    ]

DEFAULT_STATUSES_OFFER_MERGE = ['Duplicate']


# This is used by JS on the issue admin page to indicate that the user deleted
# this template, so it should not be considered when updating the project's
# issue config.
DELETED_TEMPLATE_NAME = '<DELETED>'


# This is the default maximum total bytes of files attached
# to all the issues in a project.
ISSUE_ATTACHMENTS_QUOTA_HARD = 50 * 1024 * 1024L
ISSUE_ATTACHMENTS_QUOTA_SOFT = ISSUE_ATTACHMENTS_QUOTA_HARD - 1 * 1024 * 1024L

# Default value for nav action after updating an issue.
DEFAULT_AFTER_ISSUE_UPDATE = user_pb2.IssueUpdateNav.STAY_SAME_ISSUE

# Maximum comment length to mitigate spammy comments
MAX_COMMENT_CHARS = 50 * 1024
MAX_SUMMARY_CHARS = 500

SHORT_SUMMARY_LENGTH = 45

# Number of recent commands to offer the user on the quick edit form.
MAX_RECENT_COMMANDS = 5

# These recent commands are shown if the user has no history of their own.
DEFAULT_RECENT_COMMANDS = [
    ('owner=me status=Accepted', "I'll handle this one."),
    ('owner=me Priority=High status=Accepted', "I'll look into it soon."),
    ('status=Fixed', 'The change for this is done now.'),
    ('Type=Enhancement', 'This is an enhancement, not a defect.'),
    ('status=Invalid', 'Please report this in a more appropriate place.'),
    ]

# Consider an issue to be a "noisy" issue if it has more than these:
NOISY_ISSUE_COMMENT_COUNT = 100
NOISY_ISSUE_STARRER_COUNT = 100

# After a project owner edits the filter rules, we recompute the
# derived field values in work items that each handle a chunk of
# of this many items.
RECOMPUTE_DERIVED_FIELDS_BLOCK_SIZE = 250

# This is the number of issues listed in the ReindexQueue table that will
# be processed each minute.
MAX_ISSUES_TO_REINDEX_PER_MINUTE = 500

