# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Some constants of regexes used in Monorail to validate urls and emails."""

import re
import settings

# We linkify http, https, ftp, and mailto schemes only.
LINKIFY_SCHEMES = r'https?://|ftp://|mailto:'

# This regex matches shorthand URLs that we know are valid.
# Example: go/monorail
# The scheme is optional, and if it is missing we add it to the link.
IS_A_SHORT_LINK_RE = re.compile(
    r'(?<![-/._])\b(%s)?'     # Scheme is optional for short links.
    r'(%s)'        # The list of know shorthand links from settings.py
    r'/([^\s<]+)'  # Allow anything, checked with validation code.
    % (LINKIFY_SCHEMES, '|'.join(settings.autolink_shorthand_hosts)),
    re.UNICODE)
IS_A_NUMERIC_SHORT_LINK_RE = re.compile(
    r'(?<![-/._])\b(%s)?'     # Scheme is optional for short links.
    r'(%s)'        # The list of know shorthand links from settings.py
    r'/([0-9]+)'  # Allow digits only for these domains.
    % (LINKIFY_SCHEMES, '|'.join(settings.autolink_numeric_shorthand_hosts)),
    re.UNICODE)

# This regex matches fully-formed URLs, starting with a scheme.
# Example: http://chromium.org or mailto:user@example.com
# We link to the specified URL without adding anything.
# Also count a start-tag '<' as a url delimeter, since the autolinker
# is sometimes run against html fragments.
IS_A_LINK_RE = re.compile(
    r'\b(%s)'    # Scheme must be a whole word.
    r'([^\s<]+)' # Allow anything, checked with validation code.
    % LINKIFY_SCHEMES, re.UNICODE)

# This regex matches text that looks like a URL despite lacking a scheme.
# Example: crrev.com
# Since the scheme is not specified, we prepend "http://".
IS_IMPLIED_LINK_RE = re.compile(
    r'(?<![-/._])\b[a-z]((-|\.)?[a-z0-9])+\.(com|net|org|edu)\b'  # Domain.
    r'(/[^\s<]*)?',  # Allow anything, check with validation code.
    re.UNICODE)

# This regex matches text that looks like an email address.
# Example: user@example.com
# These get linked to the user profile page if it exists, otherwise
# they become a mailto:.
IS_IMPLIED_EMAIL_RE = re.compile(
    r'\b[a-z]((-|\.)?[a-z0-9])+@'  # Username@
    r'[a-z]((-|\.)?[a-z0-9])+\.(com|net|org|edu)\b',  # Domain
    re.UNICODE)
