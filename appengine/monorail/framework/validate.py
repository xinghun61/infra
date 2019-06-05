# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of Python input field validators."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import re

# RFC 2821-compliant email address regex
#
# Please see sections "4.1.2 Command Argument Syntax" and
# "4.1.3 Address Literals" of:  http://www.faqs.org/rfcs/rfc2821.html
#
# The following implementation is still a subset of RFC 2821.  Fully
# double-quoted <user> parts are not supported (since the RFC discourages
# their use anyway), and using the backslash to escape other characters
# that are normally invalid, such as commas, is not supported.
#
# The groups in this regular expression are:
#
# <user>: all of the valid non-quoted portion of the email address before
#   the @ sign (not including the @ sign)
#
# <domain>: all of the domain name between the @ sign (but not including it)
#   and the dot before the TLD (but not including that final dot)
#
# <tld>: the top-level domain after the last dot (but not including that
#   final dot)
#
_RFC_2821_EMAIL_REGEX = r"""(?x)
  (?P<user>
    # Part of the username that comes before any dots that may occur in it.
    # At least one of the listed non-dot characters is required before the
    # first dot.
    [-a-zA-Z0-9!#$%&'*+/=?^_`{|}~]+

    # Remaining part of the username that starts with the dot and
    # which may have other dots, if such a part exists.  Only one dot
    # is permitted between each "Atom", and a trailing dot is not permitted.
    (?:[.][-a-zA-Z0-9!#$%&'*+/=?^_`{|}~]+)*
  )

  # Domain name, where subdomains are allowed.  Also, dashes are allowed
  # given that they are preceded and followed by at least one character.
  @(?P<domain>
    (?:[0-9a-zA-Z]       # at least one non-dash
       (?:[-]*           # plus zero or more dashes
          [0-9a-zA-Z]+   # plus at least one non-dash
       )*                # zero or more of dashes followed by non-dashes
    )                    # one required domain part (may be a sub-domain)

    (?:\.                # dot separator before additional sub-domain part
       [0-9a-zA-Z]       # at least one non-dash
       (?:[-]*           # plus zero or more dashes
          [0-9a-zA-Z]+   # plus at least one non-dash
       )*                # zero or more of dashes followed by non-dashes
    )*                   # at least one sub-domain part and a dot
   )
  \.                     # dot separator before TLD

  # TLD, the part after 'usernames@domain.' which can consist of 2-9
  # letters.
  (?P<tld>[a-zA-Z]{2,9})
  """

# object used with <re>.search() or <re>.sub() to find email addresses
# within a string (or with <re>.match() to find email addresses at the
# beginning of a string that may be followed by trailing characters,
# since <re>.match() implicitly anchors at the beginning of the string)
RE_EMAIL_SEARCH = re.compile(_RFC_2821_EMAIL_REGEX)

# object used with <re>.match to find strings that contain *only* a single
# email address (by adding the end-of-string anchor $)
RE_EMAIL_ONLY = re.compile('^%s$' % _RFC_2821_EMAIL_REGEX)

_SCHEME_PATTERN = r'(?:https?|ftp)://'
_SHORT_HOST_PATTERN = (
    r'(?=[a-zA-Z])[-a-zA-Z0-9]*[a-zA-Z0-9](:[0-9]+)?'
    r'/'  # Slash is manditory for short host names.
    r'[^\s]*'
    )
_DOTTED_HOST_PATTERN = (
    r'[-a-zA-Z0-9.]+\.[a-zA-Z]{2,9}(:[0-9]+)?'
    r'(/[^\s]*)?'
    )
_URL_REGEX = r'%s(%s|%s)' % (
    _SCHEME_PATTERN, _SHORT_HOST_PATTERN, _DOTTED_HOST_PATTERN)

# A more complete URL regular expression based on a combination of the
# existing _URL_REGEX and the pattern found for URI regular expressions
# found in the URL RFC document. It's detailed here:
# http://www.ietf.org/rfc/rfc2396.txt
RE_COMPLEX_URL = re.compile(r'^%s(\?([^# ]*))?(#(.*))?$' % _URL_REGEX)


def IsValidEmail(s):
  """Return true iff the string is a properly formatted email address."""
  return RE_EMAIL_ONLY.match(s)


def IsValidMailTo(s):
  """Return true iff the string is a properly formatted mailto:."""
  return s.startswith('mailto:') and RE_EMAIL_ONLY.match(s[7:])


def IsValidURL(s):
  """Return true iff the string is a properly formatted web or ftp URL."""
  return RE_COMPLEX_URL.match(s)
