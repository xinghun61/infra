# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Some constants used throughout Monorail."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
import re


# Number of seconds in various periods.
SECS_PER_MINUTE = 60
SECS_PER_HOUR = SECS_PER_MINUTE * 60
SECS_PER_DAY = SECS_PER_HOUR * 24
SECS_PER_MONTH = SECS_PER_DAY * 30
SECS_PER_YEAR = SECS_PER_DAY * 365

# When we write to memcache, let the values expire so that we don't
# get any unexpected super-old values as we make code changes over the
# years.   Also, searches can contain date terms like [opened<today-1]
# that would become wrong if cached for a long time.
MEMCACHE_EXPIRATION = 6 * SECS_PER_HOUR

# Fulltext indexing happens asynchronously and we get no notification
# when the indexing operation has completed.  So, when we cache searches
# that use fulltext terms, the results might be stale.  We still do
# cache them and use the cached values, but we expire them so that the
# results cannot be stale for a long period of time.
FULLTEXT_MEMCACHE_EXPIRATION = 3 * SECS_PER_MINUTE

# Size in bytes of the largest form submission that we will accept
MAX_POST_BODY_SIZE = 10 * 1024 * 1024   # = 10 MB

# Special user ID and name to use when no user was specified.
NO_USER_SPECIFIED = 0
NO_SESSION_SPECIFIED = 0
NO_USER_NAME = '----'
DELETED_USER_NAME = 'a_deleted_user'
DELETED_USER_ID = 1
USER_NOT_FOUND_NAME = 'user_not_found'

# Queues for deleting users tasks.
QUEUE_SEND_WIPEOUT_USER_LISTS = 'wipeoutsendusers'
QUEUE_FETCH_WIPEOUT_DELETED_USERS = 'wipeoutdeleteusers'
QUEUE_DELETE_USERS = 'deleteusers'

# We remember the time of each user's last page view, but to reduce the
# number of database writes, we only update it if it is newer by an hour.
VISIT_RESOLUTION = 1 * SECS_PER_HOUR

# String to display when some field has no value.
NO_VALUES = '----'

# If the user enters one or more dashes, that means "no value".  This is useful
# in bulk edit, inbound email, and commit log command where a blank field
# means "keep what was there" or is ignored.
NO_VALUE_RE = re.compile(r'^-+$')

# Used to loosely validate column spec. Mainly guards against malicious input.
COLSPEC_RE = re.compile(r'^[-.\w\s/]*$', re.UNICODE)
COLSPEC_COL_RE = re.compile(r'[-.\w/]+', re.UNICODE)
MAX_COL_PARTS = 25
MAX_COL_LEN = 50

# Used to loosely validate sort spec. Mainly guards against malicious input.
SORTSPEC_RE = re.compile(r'^[-.\w\s/]*$', re.UNICODE)
MAX_SORT_PARTS = 6

# For the artifact search box autosizing when the user types a long query.
MIN_ARTIFACT_SEARCH_FIELD_SIZE = 38
MAX_ARTIFACT_SEARCH_FIELD_SIZE = 75
AUTOSIZE_STEP = 3

# Regular expressions used in parsing label and status configuration text
IDENTIFIER_REGEX = r'[-.\w]+'
IDENTIFIER_RE = re.compile(IDENTIFIER_REGEX, re.UNICODE)
# Labels and status values that are prefixed by a pound-sign are not displayed
# in autocomplete menus.
IDENTIFIER_DOCSTRING_RE = re.compile(
    r'^(#?%s)[ \t]*=?[ \t]*(.*)$' % IDENTIFIER_REGEX,
    re.MULTILINE | re.UNICODE)

# Number of label text fields that we can display on a web form for issues.
MAX_LABELS = 24

# Default number of comments to display on an artifact detail page at one time.
# Other comments will be paginated.
DEFAULT_COMMENTS_PER_PAGE = 100

# Content type to use when serving JSON.
CONTENT_TYPE_JSON = 'application/json; charset=UTF-8'
CONTENT_TYPE_JSON_OPTIONS = 'nosniff'

# Maximum comments to index to keep the search index from choking.  E.g., if an
# artifact had 1200 comments, only 0..99 and 701..1200 would be indexed.
# This mainly affects advocacy issues which are highly redundant anyway.
INITIAL_COMMENTS_TO_INDEX = 100
FINAL_COMMENTS_TO_INDEX = 500

# This is the longest string that GAE search will accept in one field.
# The entire serach document is also limited to 1M, so our limit is 800
# so that the comments leave room for metadata.
MAX_FTS_FIELD_SIZE = 800 * 1024

# Base path to EZT templates.
this_dir = os.path.dirname(__file__)
TEMPLATE_PATH = this_dir[:this_dir.rindex('/')] + '/templates/'

# Defaults for dooming a project.
DEFAULT_DOOM_REASON = 'No longer needed'
DEFAULT_DOOM_PERIOD = SECS_PER_DAY * 90

MAX_PROJECT_PEOPLE = 1000
MAX_PROJECT_NAME_LENGTH = 63

MAX_HOTLIST_NAME_LENGTH = 80

# When logging potentially long debugging strings, only show this many chars.
LOGGING_MAX_LENGTH = 2000

# Maps languages supported by google-code-prettify
# to the class name that should be added to code blocks in that language.
# This list should be kept in sync with the handlers registered
# in lang-*.js and prettify.js from the prettify project.
PRETTIFY_CLASS_MAP = {
    ext: 'lang-' + ext
    for ext in [
        # Supported in lang-*.js
        'apollo', 'agc', 'aea', 'lisp', 'el', 'cl', 'scm',
        'css', 'go', 'hs', 'lua', 'fs', 'ml', 'proto', 'scala', 'sql', 'vb',
        'vbs', 'vhdl', 'vhd', 'wiki', 'yaml', 'yml', 'clj',
        # Supported in prettify.js
        'htm', 'html', 'mxml', 'xhtml', 'xml', 'xsl',
        'c', 'cc', 'cpp', 'cxx', 'cyc', 'm',
        'json', 'cs', 'java', 'bsh', 'csh', 'sh', 'cv', 'py', 'perl', 'pl',
        'pm', 'rb', 'js', 'coffee',
        ]}

# Languages which are not specifically mentioned in prettify.js
# but which render intelligibly with the default handler.
PRETTIFY_CLASS_MAP.update(
    (ext, '') for ext in [
        'hpp', 'hxx', 'hh', 'h', 'inl', 'idl', 'swig', 'd',
        'php', 'tcl', 'aspx', 'cfc', 'cfm',
        'ent', 'mod', 'as',
        'y', 'lex', 'awk', 'n', 'pde',
        ])

# Languages which are not specifically mentioned in prettify.js
# but which should be rendered using a certain prettify module.
PRETTIFY_CLASS_MAP.update({
    'docbook': 'lang-xml',
    'dtd': 'lang-xml',
    'duby': 'lang-rb',
    'mk': 'lang-sh',
    'mak': 'lang-sh',
    'make': 'lang-sh',
    'mirah': 'lang-rb',
    'ss': 'lang-lisp',
    'vcproj': 'lang-xml',
    'xsd': 'lang-xml',
    'xslt': 'lang-xml',
})

PRETTIFY_FILENAME_CLASS_MAP = {
    'makefile': 'lang-sh',
    'makefile.in': 'lang-sh',
    'doxyfile': 'lang-sh',  # Key-value pairs with hash comments
    '.checkstyle': 'lang-xml',
    '.classpath': 'lang-xml',
    '.project': 'lang-xml',
}

OAUTH_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'

FILENAME_RE = re.compile('^[-_.a-zA-Z0-9 #+()]+$')
