# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Autolink helps auto-link references to artifacts in text.

This class maintains a registry of artifact autolink syntax specs and
callbacks. The structure of that registry is:
  { component_name: (lookup_callback, match_to_reference_function,
                     { regex: substitution_callback, ...}),
    ...
  }

For example:
  { 'tracker':
     (GetReferencedIssues,
      ExtractProjectAndIssueIds,
      {_ISSUE_REF_RE: ReplaceIssueRef}),
    'versioncontrol':
     (GetReferencedRevisions,
      ExtractProjectAndRevNum,
      {_GIT_HASH_RE: ReplaceRevisionRef}),
  }

The dictionary of regexes is used here because, in the future, we
might add more regexes for each component rather than have one complex
regex per component.
"""

import logging
import re
import urllib
import urlparse

import settings
from framework import template_helpers
from framework import validate
from proto import project_pb2
from tracker import tracker_helpers


# If the total length of all comments is too large, we don't autolink.
_MAX_TOTAL_LENGTH = 50 * 1024  # 50KB
# Special all_referenced_artifacts value used to indicate that the
# text content is too big to autolink quickly.
_SKIP_AUTOLINKING = 'skip autolinking'

_CLOSING_TAG_RE = re.compile('</[a-z0-9]+>$', re.IGNORECASE)

# We linkify http, https, ftp, and mailto schemes only.
_LINKIFY_SCHEMES = r'https?://|ftp://|mailto:'

# This regex matches shorthand URLs that we know are valid.
# Example: go/monorail
# The scheme is optional, and if it is missing we add it to the link.
IS_A_SHORT_LINK_RE = re.compile(
    r'(?<![-/._])\b(%s)?'     # Scheme is optional for short links.
    r'(%s)'        # The list of know shorthand links from settings.py
    r'/([^\s<]+)'  # Allow anything, checked with validation code.
    % (_LINKIFY_SCHEMES, '|'.join(settings.autolink_shorthand_hosts)),
    re.UNICODE)
IS_A_NUMERIC_SHORT_LINK_RE = re.compile(
    r'(?<![-/._])\b(%s)?'     # Scheme is optional for short links.
    r'(%s)'        # The list of know shorthand links from settings.py
    r'/([0-9]+)'  # Allow digits only for these domains.
    % (_LINKIFY_SCHEMES, '|'.join(settings.autolink_numeric_shorthand_hosts)),
    re.UNICODE)

# This regex matches fully-formed URLs, starting with a scheme.
# Example: http://chromium.org or mailto:user@example.com
# We link to the specified URL without adding anything.
# Also count a start-tag '<' as a url delimeter, since the autolinker
# is sometimes run against html fragments.
_IS_A_LINK_RE = re.compile(
    r'\b(%s)'    # Scheme must be a whole word.
    r'([^\s<]+)' # Allow anything, checked with validation code.
    % _LINKIFY_SCHEMES, re.UNICODE)

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
_IS_IMPLIED_EMAIL_RE = re.compile(
    r'\b[a-z]((-|\.)?[a-z0-9])+@'  # Username@
    r'[a-z]((-|\.)?[a-z0-9])+\.(com|net|org|edu)\b',  # Domain
    re.UNICODE)

# These are allowed in links, but if any of closing delimiters appear
# at the end of the link, and the opening one is not part of the link,
# then trim off the closing delimiters.
_LINK_TRAILING_CHARS = [
    (None, ':'),
    (None, '.'),
    (None, ','),
    ('<', '>'),
    ("'", "'"),
    ('"', '"'),
    ('(', ')'),
    ('[', ']'),
    ('{', '}'),
    ]


def LinkifyEmail(_mr, autolink_regex_match, component_ref_artifacts):
  """Examine a textual reference and replace it with a hyperlink or not.

  This is a callback for use with the autolink feature.  The function
  parameters are standard for this type of callback.

  Args:
    _mr: unused information parsed from the HTTP request.
    autolink_regex_match: regex match for the textual reference.
    component_ref_artifacts: unused result of call to GetReferencedUsers.

  Returns:
    A list of TextRuns with tag=a linking to the user profile page of
    any defined users, otherwise a mailto: link is generated.
  """
  email = autolink_regex_match.group(0)

  if not validate.IsValidEmail(email):
    return [template_helpers.TextRun(email)]

  if email in component_ref_artifacts:
    href = '/u/%s' % email
  else:
    href = 'mailto:' + email

  result = [template_helpers.TextRun(email, tag='a', href=href)]
  return result


def CurryGetReferencedUsers(services):
  """Return a function to get ref'd users with these services objects bound.

  Currying is a convienent way to give the callback access to the services
  objects, but without requiring that all possible services objects be passed
  through the autolink registry and functions.

  Args:
    services: connection to the user persistence layer.

  Returns:
    A ready-to-use function that accepts the arguments that autolink
    expects to pass to it.
  """

  def GetReferencedUsers(mr, emails):
    """Return a dict of users referenced by these comments.

    Args:
      mr: commonly used info parsed from the request.
      ref_tuples: email address strings for each user
          that is mentioned in the comment text.

    Returns:
      A dictionary {email: user_pb} including all existing users.
    """
    user_id_dict = services.user.LookupExistingUserIDs(mr.cnxn, emails)
    users_by_id = services.user.GetUsersByIDs(mr.cnxn, user_id_dict.values())
    users_by_email = {
      email: users_by_id[user_id]
      for email, user_id in user_id_dict.iteritems()}
    return users_by_email

  return GetReferencedUsers


def Linkify(_mr, autolink_regex_match, _component_ref_artifacts):
  """Examine a textual reference and replace it with a hyperlink or not.

  This is a callback for use with the autolink feature.  The function
  parameters are standard for this type of callback.

  Args:
    _mr: unused information parsed from the HTTP request.
    autolink_regex_match: regex match for the textual reference.
    _component_ref_artifacts: unused result of call to GetReferencedIssues.

  Returns:
    A list of TextRuns with tag=a for all matched ftp, http, https and mailto
    links converted into HTML hyperlinks.
  """
  hyperlink = autolink_regex_match.group(0)

  trailing = ''
  for begin, end in _LINK_TRAILING_CHARS:
    if hyperlink.endswith(end):
      if not begin or hyperlink[:-len(end)].find(begin) == -1:
        trailing = end + trailing
        hyperlink = hyperlink[:-len(end)]

  tag_match = _CLOSING_TAG_RE.search(hyperlink)
  if tag_match:
    trailing = hyperlink[tag_match.start(0):] + trailing
    hyperlink = hyperlink[:tag_match.start(0)]

  href = hyperlink
  if not href.lower().startswith(('http', 'ftp', 'mailto')):
    # We use http because redirects for https are not all set up.
    href = 'http://' + href

  if (not validate.IsValidURL(href) and
      not (href.startswith('mailto') and validate.IsValidEmail(href[7:]))):
    return [template_helpers.TextRun(autolink_regex_match.group(0))]

  result = [template_helpers.TextRun(hyperlink, tag='a', href=href)]
  if trailing:
    result.append(template_helpers.TextRun(trailing))

  return result


# Regular expression to detect git hashes.
# Used to auto-link to Git hashes on crrev.com when displaying issue details.
# Matches "rN", "r#N", and "revision N" when "rN" is not part of a larger word
# and N is a hexadecimal string of 40 chars.
_GIT_HASH_RE = re.compile(
    r'\b(?P<prefix>r(evision\s+#?)?)?(?P<revnum>([a-f0-9]{40}))\b',
    re.IGNORECASE | re.MULTILINE)

# This is for SVN revisions and Git commit posisitons.
_SVN_REF_RE = re.compile(
    r'\b(?P<prefix>r(evision\s+#?)?)(?P<revnum>([0-9]{1,7}))\b',
    re.IGNORECASE | re.MULTILINE)


def GetReferencedRevisions(_mr, _refs):
  """Load the referenced revision objects."""
  # For now we just autolink any revision hash without actually
  # checking that such a revision exists,
  # TODO(jrobbins): Hit crrev.com and check that the revision exists
  # and show a rollover with revision info.
  return None


def ExtractRevNums(_mr, autolink_regex_match):
  """Return internal representation of a rev reference."""
  ref = autolink_regex_match.group('revnum')
  logging.debug('revision ref = %s', ref)
  return [ref]


def ReplaceRevisionRef(
    mr, autolink_regex_match, _component_ref_artifacts):
  """Return HTML markup for an autolink reference."""
  prefix = autolink_regex_match.group('prefix')
  revnum = autolink_regex_match.group('revnum')
  url = _GetRevisionURLFormat(mr.project).format(revnum=revnum)
  content = revnum
  if prefix:
    content = '%s%s' % (prefix, revnum)
  return [template_helpers.TextRun(content, tag='a', href=url)]


def _GetRevisionURLFormat(project):
  # TODO(jrobbins): Expose a UI to customize it to point to whatever site
  # hosts the source code. Also, site-wide default.
  return (project.revision_url_format or settings.revision_url_format)


# Regular expression to detect issue references.
# Used to auto-link to other issues when displaying issue details.
# Matches "issue " when "issue" is not part of a larger word, or
# "issue #", or just a "#" when it is preceeded by a space.
_ISSUE_REF_RE = re.compile(r"""
    (?P<prefix>\b(issues?|bugs?)[ \t]*(:|=)?)
    ([ \t]*(?P<project_name>\b[-a-z0-9]+[:\#])?
     (?P<number_sign>\#?)
     (?P<local_id>\d+)\b
     (,?[ \t]*(and|or)?)?)+""", re.IGNORECASE | re.VERBOSE)

# This is for chromium.org's crbug.com shorthand domain.
_CRBUG_REF_RE = re.compile(r"""
    (?P<prefix>\b(https?://)?crbug.com/)
    ((?P<project_name>\b[-a-z0-9]+)(?P<separator>/))?
    (?P<local_id>\d+)\b
    (?P<anchor>\#c[0-9]+)?""", re.IGNORECASE | re.VERBOSE)

# Once the overall issue reference has been detected, pick out the specific
# issue project:id items within it.  Often there is just one, but the "and|or"
# syntax can allow multiple issues.
_SINGLE_ISSUE_REF_RE = re.compile(r"""
    (?P<prefix>\b(issue|bug)[ \t]*)?
    (?P<project_name>\b[-a-z0-9]+[:\#])?
    (?P<number_sign>\#?)
    (?P<local_id>\d+)\b""", re.IGNORECASE | re.VERBOSE)


def CurryGetReferencedIssues(services):
  """Return a function to get ref'd issues with these services objects bound.

  Currying is a convienent way to give the callback access to the services
  objects, but without requiring that all possible services objects be passed
  through the autolink registry and functions.

  Args:
    services: connection to issue, config, and project persistence layers.

  Returns:
    A ready-to-use function that accepts the arguments that autolink
    expects to pass to it.
  """

  def GetReferencedIssues(mr, ref_tuples):
    """Return lists of open and closed issues referenced by these comments.

    Args:
      mr: commonly used info parsed from the request.
      ref_tuples: list of (project_name, local_id) tuples for each issue
          that is mentioned in the comment text. The project_name may be None,
          in which case the issue is assumed to be in the current project.

    Returns:
      A list of open and closed issue dicts.
    """
    ref_projects = services.project.GetProjectsByName(
        mr.cnxn,
        [(ref_pn or mr.project_name) for ref_pn, _ in ref_tuples])
    issue_ids, _misses = services.issue.ResolveIssueRefs(
        mr.cnxn, ref_projects, mr.project_name, ref_tuples)
    open_issues, closed_issues = (
        tracker_helpers.GetAllowedOpenedAndClosedIssues(
            mr, issue_ids, services))

    open_dict = {}
    for issue in open_issues:
      open_dict[_IssueProjectKey(issue.project_name, issue.local_id)] = issue

    closed_dict = {}
    for issue in closed_issues:
      closed_dict[_IssueProjectKey(issue.project_name, issue.local_id)] = issue

    logging.info('autolinking dicts %r and %r', open_dict, closed_dict)

    return open_dict, closed_dict

  return GetReferencedIssues


def _ParseProjectNameMatch(project_name):
  """Process the passed project name and determine the best representation.

  Args:
    project_name: a string with the project name matched in a regex

  Returns:
    A minimal representation of the project name, None if no valid content.
  """
  if not project_name:
    return None
  return project_name.lstrip().rstrip('#: \t\n')


def _ExtractProjectAndIssueIds(
    autolink_regex_match, subregex, default_project_name=None):
  """Convert a regex match for a textual reference into our internal form."""
  whole_str = autolink_regex_match.group(0)
  refs = []
  for submatch in subregex.finditer(whole_str):
    project_name = (
        _ParseProjectNameMatch(submatch.group('project_name')) or
        default_project_name)
    ref = (project_name, int(submatch.group('local_id')))
    refs.append(ref)
    logging.info('issue ref = %s', ref)

  return refs


def ExtractProjectAndIssueIdsNormal(_mr, autolink_regex_match):
  """Convert a regex match for a textual reference into our internal form."""
  return _ExtractProjectAndIssueIds(
      autolink_regex_match, _SINGLE_ISSUE_REF_RE)


def ExtractProjectAndIssueIdsCrBug(_mr, autolink_regex_match):
  """Convert a regex match for a textual reference into our internal form."""
  return _ExtractProjectAndIssueIds(
      autolink_regex_match, _CRBUG_REF_RE, default_project_name='chromium')


# This uses project name to avoid a lookup on project ID in a function
# that has no services object.
def _IssueProjectKey(project_name, local_id):
  """Make a dictionary key to identify a referenced issue."""
  return '%s:%d' % (project_name, local_id)


class IssueRefRun(object):
  """A text run that links to a referenced issue."""

  def __init__(self, issue, is_closed, project_name, content, anchor):
    self.tag = 'a'
    self.css_class = 'closed_ref' if is_closed else None
    self.title = issue.summary
    self.href = '/p/%s/issues/detail?id=%d%s' % (
        project_name, issue.local_id, anchor)

    self.content = content
    if is_closed:
      self.content = ' %s ' % self.content


def _ReplaceIssueRef(
    autolink_regex_match, component_ref_artifacts, single_issue_regex,
    default_project_name):
  """Examine a textual reference and replace it with an autolink or not.

  Args:
    autolink_regex_match: regex match for the textual reference.
    component_ref_artifacts: result of earlier call to GetReferencedIssues.
    single_issue_regex: regular expression to parse individual issue references
        out of a multi-issue-reference phrase.  E.g., "issues 12 and 34".
    default_project_name: project name to use when not specified.

  Returns:
    A list of IssueRefRuns and TextRuns to replace the textual
    reference.  If there is an issue to autolink to, we return an HTML
    hyperlink.  Otherwise, we the run will have the original plain
    text.
  """
  open_dict, closed_dict = component_ref_artifacts
  original = autolink_regex_match.group(0)
  logging.info('called ReplaceIssueRef on %r', original)
  result_runs = []
  pos = 0
  for submatch in single_issue_regex.finditer(original):
    if submatch.start() >= pos:
      if original[pos: submatch.start()]:
        result_runs.append(template_helpers.TextRun(
            original[pos: submatch.start()]))
      replacement_run = _ReplaceSingleIssueRef(
          submatch, open_dict, closed_dict, default_project_name)
      result_runs.append(replacement_run)
      pos = submatch.end()

  if original[pos:]:
    result_runs.append(template_helpers.TextRun(original[pos:]))

  return result_runs


def ReplaceIssueRefNormal(mr, autolink_regex_match, component_ref_artifacts):
  """Replaces occurances of 'issue 123' with link TextRuns as needed."""
  return _ReplaceIssueRef(
      autolink_regex_match, component_ref_artifacts,
      _SINGLE_ISSUE_REF_RE, mr.project_name)


def ReplaceIssueRefCrBug(_mr, autolink_regex_match, component_ref_artifacts):
  """Replaces occurances of 'crbug.com/123' with link TextRuns as needed."""
  return _ReplaceIssueRef(
      autolink_regex_match, component_ref_artifacts,
      _CRBUG_REF_RE, 'chromium')


def _ReplaceSingleIssueRef(
    submatch, open_dict, closed_dict, default_project_name):
  """Replace one issue reference with a link, or the original text."""
  content = submatch.group(0)
  project_name = submatch.group('project_name')
  anchor = submatch.groupdict().get('anchor') or ''
  if project_name:
    project_name = project_name.lstrip().rstrip(':#')
  else:
    # We need project_name for the URL, even if it is not in the text.
    project_name = default_project_name

  local_id = int(submatch.group('local_id'))
  issue_key = _IssueProjectKey(project_name, local_id)
  if issue_key in open_dict:
    return IssueRefRun(
        open_dict[issue_key], False, project_name, content, anchor)
  elif issue_key in closed_dict:
    return IssueRefRun(
        closed_dict[issue_key], True, project_name, content, anchor)
  else:  # Don't link to non-existent issues.
    return template_helpers.TextRun(content)


class Autolink(object):
  """Maintains a registry of autolink syntax and can apply it to comments."""

  def __init__(self):
    self.registry = {}

  def RegisterComponent(self, component_name, artifact_lookup_function,
                        match_to_reference_function, autolink_re_subst_dict):
    """Register all the autolink info for a software component.

    Args:
      component_name: string name of software component, must be unique.
      artifact_lookup_function: function to batch lookup all artifacts that
          might have been referenced in a set of comments:
          function(all_matches) -> referenced_artifacts
          the referenced_artifacts will be pased to each subst function.
      match_to_reference_function: convert a regex match object to
          some internal representation of the artifact reference.
      autolink_re_subst_dict: dictionary of regular expressions and
          the substitution function that should be called for each match:
          function(match, referenced_artifacts) -> replacement_markup
    """
    self.registry[component_name] = (artifact_lookup_function,
                                     match_to_reference_function,
                                     autolink_re_subst_dict)

  def GetAllReferencedArtifacts(
      self, mr, comment_text_list, max_total_length=_MAX_TOTAL_LENGTH):
    """Call callbacks to lookup all artifacts possibly referenced.

    Args:
      mr: information parsed out of the user HTTP request.
      comment_text_list: list of comment content strings.
      max_total_length: int max number of characters to accept:
          if more than this, then skip autolinking entirely.

    Returns:
      Opaque object that can be pased to MarkupAutolinks.  It's
      structure happens to be {component_name: artifact_list, ...},
      or the special value _SKIP_AUTOLINKING.
    """
    total_len = sum(len(comment_text) for comment_text in comment_text_list)
    if total_len > max_total_length:
      return _SKIP_AUTOLINKING

    all_referenced_artifacts = {}
    for comp, (lookup, match_to_refs, re_dict) in self.registry.iteritems():
      refs = set()
      for comment_text in comment_text_list:
        for regex in re_dict:
          for match in regex.finditer(comment_text):
            additional_refs = match_to_refs(mr, match)
            if additional_refs:
              refs.update(additional_refs)

      all_referenced_artifacts[comp] = lookup(mr, refs)

    return all_referenced_artifacts

  def MarkupAutolinks(self, mr, text_runs, all_referenced_artifacts):
    """Loop over components and regexes, applying all substitutions.

    Args:
      mr: info parsed from the user's HTTP request.
      text_runs: List of text runs for the user's comment.
      all_referenced_artifacts: result of previous call to
        GetAllReferencedArtifacts.

    Returns:
      List of text runs for the entire user comment, some of which may have
      attribures that cause them to render as links in render-rich-text.ezt.
    """
    if all_referenced_artifacts == _SKIP_AUTOLINKING:
      return text_runs

    items = self.registry.items()
    items.sort()  # Process components in determinate alphabetical order.
    for component, (_lookup, _match_ref, re_subst_dict) in items:
      component_ref_artifacts = all_referenced_artifacts[component]
      for regex, subst_fun in re_subst_dict.iteritems():
        text_runs = self._ApplySubstFunctionToRuns(
            text_runs, regex, subst_fun, mr, component_ref_artifacts)

    return text_runs

  def _ApplySubstFunctionToRuns(
      self, text_runs, regex, subst_fun, mr, component_ref_artifacts):
    """Apply autolink regex and substitution function to each text run.

    Args:
      text_runs: list of TextRun objects with parts of the original comment.
      regex: Regular expression for detecting textual references to artifacts.
      subst_fun: function to return autolink markup, or original text.
      mr: common info parsed from the user HTTP request.
      component_ref_artifacts: already-looked-up destination artifacts to use
        when computing substitution text.

    Returns:
      A new list with more and smaller runs, some of which may have tag
      and link attributes set.
    """
    result_runs = []
    for run in text_runs:
      content = run.content
      if run.tag:
        # This chunk has already been substituted, don't allow nested
        # autolinking to mess up our output.
        result_runs.append(run)
      else:
        pos = 0
        for match in regex.finditer(content):
          if match.start() > pos:
            result_runs.append(template_helpers.TextRun(
                content[pos: match.start()]))
          replacement_runs = subst_fun(mr, match, component_ref_artifacts)
          result_runs.extend(replacement_runs)
          pos = match.end()

        if run.content[pos:]:  # Keep any text that came after the last match
          result_runs.append(template_helpers.TextRun(run.content[pos:]))

    # TODO(jrobbins): ideally we would merge consecutive plain text runs
    # so that regexes can match across those run boundaries.

    return result_runs


def RegisterAutolink(services):
  """Register all the autolink hooks."""
  # The order of the RegisterComponent() calls does not matter so that we could
  # do this registration from separate modules in the future if needed.
  # Priority order of application is determined by the names of the registered
  # handers, which are sorted in MarkupAutolinks().

  services.autolink.RegisterComponent(
      '01-tracker-crbug',
      CurryGetReferencedIssues(services),
      ExtractProjectAndIssueIdsCrBug,
      {_CRBUG_REF_RE: ReplaceIssueRefCrBug})

  services.autolink.RegisterComponent(
      '02-linkify-full-urls',
      lambda request, mr: None,
      lambda mr, match: None,
      {_IS_A_LINK_RE: Linkify})

  services.autolink.RegisterComponent(
      '03-linkify-user-profiles-or-mailto',
      CurryGetReferencedUsers(services),
      lambda _mr, match: [match.group(0)],
      {_IS_IMPLIED_EMAIL_RE: LinkifyEmail})

  services.autolink.RegisterComponent(
      '04-tracker-regular',
      CurryGetReferencedIssues(services),
      ExtractProjectAndIssueIdsNormal,
      {_ISSUE_REF_RE: ReplaceIssueRefNormal})

  services.autolink.RegisterComponent(
      '05-linkify-shorthand',
      lambda request, mr: None,
      lambda mr, match: None,
      {IS_A_SHORT_LINK_RE: Linkify,
       IS_A_NUMERIC_SHORT_LINK_RE: Linkify,
       IS_IMPLIED_LINK_RE: Linkify,
       })

  services.autolink.RegisterComponent(
      '06-versioncontrol',
      GetReferencedRevisions,
      ExtractRevNums,
      {_GIT_HASH_RE: ReplaceRevisionRef,
       _SVN_REF_RE: ReplaceRevisionRef})
