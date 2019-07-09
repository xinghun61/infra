# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions to extract information from commit log data."""

import re
from collections import defaultdict


BUG_LINE_REGEX = re.compile(
    r'(?m)^(?P<flag>[>\s]*(?:BUGS?|ISSUE|Bugs?) *[ :=] *)(?P<data>.*)$')

PROJECT_NAME_REGEX = r'(?P<project>[a-z0-9][-a-z0-9]*[a-z0-9])'
BUG_NUMBER_REGEX = r'(?P<bugnum>[0-9]+)'

SHORTFORM_REGEX = r'^(?:%s:)?#?%s$' % (
    PROJECT_NAME_REGEX, BUG_NUMBER_REGEX)
CRBUG_REGEX = r'^(?:https?://)?crbug\.com/(%s/)?%s$' % (
    PROJECT_NAME_REGEX, BUG_NUMBER_REGEX)
MONORAIL_REGEX = r'^(?:https?://)?bugs\.chromium\.org/p/%s/[^?]+\?id=%s$' % (
    PROJECT_NAME_REGEX, BUG_NUMBER_REGEX)
CODESITE_REGEX = '^(?:https?://)?code\.google\.com/p/%s/[^?]+\?id=%s$' % (
    PROJECT_NAME_REGEX, BUG_NUMBER_REGEX)

REGEXES = [
    re.compile(SHORTFORM_REGEX),
    re.compile(CRBUG_REGEX),
    re.compile(MONORAIL_REGEX),
    re.compile(CODESITE_REGEX),
]


def normalize_project_name(project): # pragma: no cover
  """Return the canonical name for a project specification."""
  mapping = {
      'nacl': 'nativeclient',
      'cros': 'chromium-os',
      }
  return mapping.get(project, project)

FOOTER_PATTERN = re.compile(r'^\s*Bugdroid-Send-Email: (.*)$')

def should_send_email(commit_message):
  """If bugdroid should send email for a given commit message.
  """
  if not commit_message:
    return True

  msg_lines = list(reversed(commit_message.splitlines()))
  while not msg_lines[0] and msg_lines:
    msg_lines = msg_lines[1:]

  send_email_lines = []
  for line in msg_lines:
    if not line:
      break

    m = FOOTER_PATTERN.match(line)
    if m:
      send_email_lines.append(m.group(1))

  return not any(
      line for line in send_email_lines if line.lower() in ('no', 'false'))

def get_issues(log_entry, default_project): # pragma: no cover
  """Extract bug #'s from a SCM commit log message.

  Args:
    log_entry: The commit log_entry to search for bug #'s.
    default_project: If a bug doesn't have an project specifier (e.g. foo:123),
      then assume it belongs in this project.

  Returns:
    Dictionary of {'project': [list, of, bug, numbers]}.

  Supported Identifier Syntax:
  ----------------------------
  BUG=n
  BUG n
  BUG:n
    Matches issue 'n' in the default issue tracker (as determined by caller).

  BUG=project:n
  BUG project:n
  BUG:project:n
    Matches issue 'n' in the issue tracker for 'project'.

  BUG=<Issue Tracker URL>
    A direct link to an issue tracker page matches that issue in that project.

  Syntax Notes:
  - The keywords 'BUG' and 'ISSUE' are interchangeable in all formats.
  - 'n' can be a comma-delimited list of bug #'s.
  - Multiple bug lines may appear in the log message.
  - Project specification only works for configured projects, since we can't
    assume bugdroid has the ability to update bugs on arbitrary projects.
  """
  if not log_entry.msg:
    return {}

  bug_dict = defaultdict(set)
  default_project = normalize_project_name(default_project)

  bug_lines = [m.groupdict() for m in
               re.finditer(BUG_LINE_REGEX, log_entry.msg)]
  for line in bug_lines:
    # Store any project name found while processing the bug line and apply it
    # to subsequent bugs on the same line. This allows the shorthand syntax:
    #   project:123,456,789
    # in place of the more explicit:
    #   project:123,project:456,project:789
    #
    # Note that this means you can't follow a project-specific bug with a "bare"
    # bug (you'd have to either put the "bare" bug first, or on a separate BUG
    # line), but that seems to be the behavior most people expect, so this just
    # codifies that.
    line_project = default_project
    for ref in re.split(r'[\s,;]+', line.get('data', '')):
      for regex in REGEXES:
        m = regex.match(ref)
        if m is None:
          continue
        bugproject = m.groupdict().get('project') or line_project
        bugproject = normalize_project_name(bugproject)
        bugnum = m.groupdict().get('bugnum')
        # Only check for None, since empty project name is the default.
        bug_dict[bugproject].add(bugnum)
        line_project = bugproject

  rtn = {proj: sorted([int(b.strip()) for b in bugs])
         for proj, bugs in bug_dict.iteritems()}
  return rtn
