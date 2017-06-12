# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the autolink feature."""

import re
import unittest

from features import autolink
from framework import template_helpers
from proto import tracker_pb2
from testing import fake
from testing import testing_helpers


SIMPLE_EMAIL_RE = re.compile(r'([a-z]+)@([a-z]+)\.com')
OVER_AMBITIOUS_DOMAIN_RE = re.compile(r'([a-z]+)\.(com|net|org)')


class AutolinkTest(unittest.TestCase):

  def RegisterEmailCallbacks(self, aa):

    def LookupUsers(_mr, all_addresses):
      """Return user objects for only users who are at trusted domains."""
      return [addr for addr in all_addresses
              if addr.endswith('@example.com')]

    def Match2Addresses(_mr, match):
      return [match.group(0)]

    def MakeMailtoLink(_mr, match, comp_ref_artifacts):
      email = match.group(0)
      if email in comp_ref_artifacts:
        return [template_helpers.TextRun(
            tag='a', href='mailto:%s' % email, content=email)]
      else:
        return [template_helpers.TextRun('%s AT %s.com' % match.group(1, 2))]

    aa.RegisterComponent('testcomp',
                         LookupUsers,
                         Match2Addresses,
                         {SIMPLE_EMAIL_RE: MakeMailtoLink})

  def RegisterDomainCallbacks(self, aa):

    def LookupDomains(_mr, _all_refs):
      """Return business objects for only real domains. Always just True."""
      return True  # We don't have domain business objects, accept anything.

    def Match2Domains(_mr, match):
      return [match.group(0)]

    def MakeHyperLink(_mr, match, _comp_ref_artifacts):
      domain = match.group(0)
      return [template_helpers.TextRun(tag='a', href=domain, content=domain)]

    aa.RegisterComponent('testcomp2',
                         LookupDomains,
                         Match2Domains,
                         {OVER_AMBITIOUS_DOMAIN_RE: MakeHyperLink})

  def setUp(self):
    self.aa = autolink.Autolink()
    self.RegisterEmailCallbacks(self.aa)
    self.comment1 = ('Feel free to contact me at a@other.com, '
                     'or b@example.com, or c@example.org.')
    self.comment2 = 'no matches in this comment'
    self.comment3 = 'just matches with no ref: a@other.com, c@example.org'
    self.comments = [self.comment1, self.comment2, self.comment3]

  def testRegisterComponent(self):
    self.assertIn('testcomp', self.aa.registry)

  def testGetAllReferencedArtifacts(self):
    all_ref_artifacts = self.aa.GetAllReferencedArtifacts(
        None, self.comments)

    self.assertIn('testcomp', all_ref_artifacts)
    comp_refs = all_ref_artifacts['testcomp']
    self.assertIn('b@example.com', comp_refs)
    self.assertTrue(len(comp_refs) == 1)

  def testMarkupAutolinks(self):
    all_ref_artifacts = self.aa.GetAllReferencedArtifacts(None, self.comments)
    result = self.aa.MarkupAutolinks(
        None, [template_helpers.TextRun(self.comment1)], all_ref_artifacts)
    self.assertEqual('Feel free to contact me at ', result[0].content)
    self.assertEqual('a AT other.com', result[1].content)
    self.assertEqual(', or ', result[2].content)
    self.assertEqual('b@example.com', result[3].content)
    self.assertEqual('mailto:b@example.com', result[3].href)
    self.assertEqual(', or c@example.org.', result[4].content)

    result = self.aa.MarkupAutolinks(
        None, [template_helpers.TextRun(self.comment2)], all_ref_artifacts)
    self.assertEqual('no matches in this comment', result[0].content)

    result = self.aa.MarkupAutolinks(
        None, [template_helpers.TextRun(self.comment3)], all_ref_artifacts)
    self.assertEqual('just matches with no ref: ', result[0].content)
    self.assertEqual('a AT other.com', result[1].content)
    self.assertEqual(', c@example.org', result[2].content)

  def testNonnestedAutolinks(self):
    """Test that when a substitution yields plain text, others are applied."""
    self.RegisterDomainCallbacks(self.aa)
    all_ref_artifacts = self.aa.GetAllReferencedArtifacts(None, self.comments)
    result = self.aa.MarkupAutolinks(
        None, [template_helpers.TextRun(self.comment1)], all_ref_artifacts)
    self.assertEqual('Feel free to contact me at ', result[0].content)
    self.assertEqual('a AT ', result[1].content)
    self.assertEqual('other.com', result[2].content)
    self.assertEqual('other.com', result[2].href)
    self.assertEqual(', or ', result[3].content)
    self.assertEqual('b@example.com', result[4].content)
    self.assertEqual('mailto:b@example.com', result[4].href)
    self.assertEqual(', or c@', result[5].content)
    self.assertEqual('example.org', result[6].content)
    self.assertEqual('example.org', result[6].href)
    self.assertEqual('.', result[7].content)

    result = self.aa.MarkupAutolinks(
        None, [template_helpers.TextRun(self.comment2)], all_ref_artifacts)
    self.assertEqual('no matches in this comment', result[0].content)
    result = self.aa.MarkupAutolinks(
        None, [template_helpers.TextRun(self.comment3)], all_ref_artifacts)
    self.assertEqual('just matches with no ref: ', result[0].content)
    self.assertEqual('a AT ', result[1].content)
    self.assertEqual('other.com', result[2].content)
    self.assertEqual('other.com', result[2].href)
    self.assertEqual(', c@', result[3].content)
    self.assertEqual('example.org', result[4].content)
    self.assertEqual('example.org', result[4].href)


class EmailAutolinkTest(unittest.TestCase):

  def setUp(self):
    self.user_1 = 'fake user'  # Note: no User fields are accessed.

  def DoLinkify(self, content, filter_re=autolink._IS_IMPLIED_EMAIL_RE):
    """Calls the LinkifyEmail method and returns the result.

    Args:
      content: string with a hyperlink.

    Returns:
      A list of TextRuns with some runs having the embedded email hyperlinked.
      Or, None if no link was detected.
    """
    match = filter_re.search(content)
    if not match:
      return None

    return autolink.LinkifyEmail(None, match, {'one@example.com': self.user_1})

  def testLinkifyEmail(self):
    """Test that an address is autolinked when put in the given context."""
    test = 'one@ or @one'
    result = self.DoLinkify('Have you met %s' % test)
    self.assertEqual(None, result)

    test = 'one@example.com'
    result = self.DoLinkify('Have you met %s' % test)
    self.assertEqual('/u/' + test, result[0].href)
    self.assertEqual(test, result[0].content)

    test = 'alias@example.com'
    result = self.DoLinkify('Please also CC %s' % test)
    self.assertEqual('mailto:' + test, result[0].href)
    self.assertEqual(test, result[0].content)

    result = self.DoLinkify('Reviewed-By: Test Person <%s>' % test)
    self.assertEqual('mailto:' + test, result[0].href)
    self.assertEqual(test, result[0].content)


class URLAutolinkTest(unittest.TestCase):

  def DoLinkify(self, content, filter_re=autolink._IS_A_LINK_RE):
    """Calls the linkify method and returns the result.

    Args:
      content: string with a hyperlink.

    Returns:
      A list of TextRuns with some runs will have the embedded URL hyperlinked.
      Or, None if no link was detected.
    """
    match = filter_re.search(content)
    if not match:
      return None

    return autolink.Linkify(None, match, None)

  def testLinkify(self):
    """Test that given url is autolinked when put in the given context."""
    # Disallow the linking of URLs with user names and passwords.
    test = 'http://user:pass@www.yahoo.com'
    result = self.DoLinkify('What about %s' % test)
    self.assertEqual(None, result[0].tag)
    self.assertEqual(None, result[0].href)
    self.assertEqual(test, result[0].content)

    # Disallow the linking of non-HTTP(S) links
    test = 'nntp://news.google.com'
    result = self.DoLinkify('%s' % test)
    self.assertEqual(None, result)

    # Disallow the linking of file links
    test = 'file://C:/Windows/System32/cmd.exe'
    result = self.DoLinkify('%s' % test)
    self.assertEqual(None, result)

    # Test some known URLs
    test = 'http://www.example.com'
    result = self.DoLinkify('What about %s' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)

  def testLinkify_FTP(self):
    """Test that FTP urls are linked."""
    # Check for a standard ftp link
    test = 'ftp://ftp.example.com'
    result = self.DoLinkify('%s' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)

  def testLinkify_Email(self):
    """Test that mailto: urls are linked."""
    test = 'mailto:user@example.com'
    result = self.DoLinkify('%s' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)

  def testLinkify_ShortLink(self):
    """Test that shortlinks are linked."""
    test = 'http://go/monorail'
    result = self.DoLinkify('%s' % test, filter_re=autolink._IS_A_SHORT_LINK_RE)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)

    test = 'go/monorail'
    result = self.DoLinkify('%s' % test, filter_re=autolink._IS_A_SHORT_LINK_RE)
    self.assertEqual('http://' + test, result[0].href)
    self.assertEqual(test, result[0].content)

  def testLinkify_ImpliedLink(self):
    """Test that text with .com, .org, .net, and .edu are linked."""
    test = 'google.org'
    result = self.DoLinkify('%s' % test, filter_re=autolink._IS_IMPLIED_LINK_RE)
    self.assertEqual('http://' + test, result[0].href)
    self.assertEqual(test, result[0].content)

    test = 'code.google.com/p/chromium'
    result = self.DoLinkify('%s' % test, filter_re=autolink._IS_IMPLIED_LINK_RE)
    self.assertEqual('http://' + test, result[0].href)
    self.assertEqual(test, result[0].content)

    # This is not a domain, it is a directory or something.
    test = 'build.out/p/chromium'
    result = self.DoLinkify('%s' % test, filter_re=autolink._IS_IMPLIED_LINK_RE)
    self.assertEqual(None, result)

    # We do not link the NNTP scheme, but the domain name part of it can be
    # linked as an HTTP link.
    test = 'nntp://news.google.com'
    result = self.DoLinkify('%s' % test, filter_re=autolink._IS_IMPLIED_LINK_RE)
    self.assertEqual('http://news.google.com', result[0].href)
    self.assertEqual('news.google.com', result[0].content)

  def testLinkify_Context(self):
    """Test that surrounding syntax is not considered part of the url."""
    test = 'http://www.example.com'

    # Check for a link followed by a comma at end of English phrase.
    result = self.DoLinkify('The URL %s, points to a great website.' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual(',', result[1].content)

    # Check for a link followed by a period at end of English sentence.
    result = self.DoLinkify('The best site ever, %s.' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('.', result[1].content)

    # Check for a link in paranthesis (), [], or {}
    result = self.DoLinkify('My fav site (%s).' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual(').', result[1].content)

    result = self.DoLinkify('My fav site [%s].' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('].', result[1].content)

    result = self.DoLinkify('My fav site {%s}.' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('}.', result[1].content)

    # Check for a link with trailing colon
    result = self.DoLinkify('Hit %s: you will love it.' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual(':', result[1].content)

    # Check link with commas in query string, but don't include trailing comma.
    test = 'http://www.example.com/?v=1,2,3'
    result = self.DoLinkify('Try %s, ok?' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)

    # Check link surrounded by angle-brackets.
    result = self.DoLinkify('<%s>' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('>', result[1].content)

    # Check link surrounded by double-quotes.
    result = self.DoLinkify('"%s"' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('"', result[1].content)

    # Check link with embedded double-quotes.
    test = 'http://www.example.com/?q="a+b+c"'
    result = self.DoLinkify('Try %s, ok?' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual(',', result[1].content)

    # Check link surrounded by single-quotes.
    result = self.DoLinkify("'%s'" % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual("'", result[1].content)

    # Check link with embedded single-quotes.
    test = "http://www.example.com/?q='a+b+c'"
    result = self.DoLinkify('Try %s, ok?' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual(',', result[1].content)

    # Check link with embedded parens.
    test = 'http://www.example.com/funky(foo)and(bar).asp'
    result = self.DoLinkify('Try %s, ok?' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual(',', result[1].content)

    test = 'http://www.example.com/funky(foo)and(bar).asp'
    result = self.DoLinkify('My fav site <%s>' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('>', result[1].content)

    # Check link with embedded brackets and braces.
    test = 'http://www.example.com/funky[foo]and{bar}.asp'
    result = self.DoLinkify('My fav site <%s>' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('>', result[1].content)

    # Check link with mismatched delimeters inside it or outside it.
    test = 'http://www.example.com/funky"(foo]and>bar}.asp'
    result = self.DoLinkify('My fav site <%s>' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('>', result[1].content)

    test = 'http://www.example.com/funky"(foo]and>bar}.asp'
    result = self.DoLinkify('My fav site {%s' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)

    test = 'http://www.example.com/funky"(foo]and>bar}.asp'
    result = self.DoLinkify('My fav site %s}' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('}', result[1].content)

    # Link as part of an HTML example.
    test = 'http://www.example.com/'
    result = self.DoLinkify('<a href="%s">' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)
    self.assertEqual('">', result[1].content)

    # Link nested in an HTML tag.
    result = self.DoLinkify('<span>%s</span>' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)

    # Link followed by HTML tag - same bug as above.
    result = self.DoLinkify('%s<span>foo</span>' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)

    # Link followed by unescaped HTML tag.
    result = self.DoLinkify('%s<span>foo</span>' % test)
    self.assertEqual(test, result[0].href)
    self.assertEqual(test, result[0].content)

  def testLinkify_ContextOnBadLink(self):
    """Test that surrounding text retained in cases where we don't link url."""
    test = 'http://bad=example'
    result = self.DoLinkify('<a href="%s">' % test)
    self.assertEqual(None, result[0].href)
    self.assertEqual(test + '">', result[0].content)
    self.assertEqual(1, len(result))

  def testLinkify_UnicodeContext(self):
    """Test that unicode context does not mess up the link."""
    test = 'http://www.example.com'

    # This string has a non-breaking space \xa0.
    result = self.DoLinkify(u'The correct RFC link is\xa0%s' % test)
    self.assertEqual(test, result[0].content)
    self.assertEqual(test, result[0].href)

  def testLinkify_UnicodeLink(self):
    """Test that unicode in a link is OK."""
    test = u'http://www.example.com?q=division\xc3\xb7sign'

    # This string has a non-breaking space \xa0.
    result = self.DoLinkify(u'The unicode link is %s' % test)
    self.assertEqual(test, result[0].content)
    self.assertEqual(test, result[0].href)

  def testLinkify_LinkTextEscapingDisabled(self):
    """Test that url-like things that miss validation aren't linked."""
    # Link matched by the regex but not accepted by the validator.
    test = 'http://bad_domain/reportdetail?reportid=35aa03e04772358b'
    result = self.DoLinkify('<span>%s</span>' % test)
    self.assertEqual(None, result[0].href)
    self.assertEqual(test, result[0].content)


def _Issue(project_name, local_id, summary, status):
  issue = tracker_pb2.Issue()
  issue.project_name = project_name
  issue.local_id = local_id
  issue.summary = summary
  issue.status = status
  return issue


class TrackerAutolinkTest(unittest.TestCase):

  COMMENT_TEXT = (
    'This relates to issue 1, issue #2, and issue3 \n'
    'as well as bug 4, bug #5, and bug6 \n'
    'with issue other-project:12 and issue other-project#13. \n'
    'Watch out for issues 21, 22, and 23 with oxford comma. \n'
    'And also bugs 31, 32 and 33 with no oxford comma.\n'
    'Here comes crbug.com/123 and crbug.com/monorail/456.\n'
    'We do not match when an issue\n'
    '999. Is split across lines.'
    )

  def testExtractProjectAndIssueIdNormal(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail?id=1')
    ref_batches = []
    for match in autolink._ISSUE_REF_RE.finditer(self.COMMENT_TEXT):
      new_refs = autolink.ExtractProjectAndIssueIdsNormal(mr, match)
      ref_batches.append(new_refs)

    self.assertEquals(
      ref_batches,
      [[(None, 1)],
       [(None, 2)],
       [(None, 3)],
       [(None, 4)],
       [(None, 5)],
       [(None, 6)],
       [('other-project', 12)],
       [('other-project', 13)],
       [(None, 21), (None, 22), (None, 23)],
       [(None, 31), (None, 32), (None, 33)],
       ])


  def testExtractProjectAndIssueIdCrbug(self):
    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/issues/detail?id=1')
    ref_batches = []
    for match in autolink._CRBUG_REF_RE.finditer(self.COMMENT_TEXT):
      new_refs = autolink.ExtractProjectAndIssueIdsCrBug(mr, match)
      ref_batches.append(new_refs)

    self.assertEquals(
      ref_batches,
      [[('chromium', 123)],
       [('monorail', 456)],
      ])

  def DoReplaceIssueRef(
      self, content, regex=autolink._ISSUE_REF_RE,
      single_issue_regex=autolink._SINGLE_ISSUE_REF_RE,
      default_project_name=None):
    """Calls the ReplaceIssueRef method and returns the result.

    Args:
      content: string that may have a textual reference to an issue.
      regex: optional regex to use instead of _ISSUE_REF_RE.

    Returns:
      A list of TextRuns with some runs will have the reference hyperlinked.
      Or, None if no reference detected.
    """
    match = regex.search(content)
    if not match:
      return None

    open_dict = {'proj:1': _Issue('proj', 1, 'summary-PROJ-1', 'New'),
                 # Assume there is no issue 3 in PROJ
                 'proj:4': _Issue('proj', 4, 'summary-PROJ-4', 'New'),
                 'proj:6': _Issue('proj', 6, 'summary-PROJ-6', 'New'),
                 'other-project:12': _Issue('other-project', 12,
                                            'summary-OP-12', 'Accepted'),
                }
    closed_dict = {'proj:2': _Issue('proj', 2, 'summary-PROJ-2', 'Fixed'),
                   'proj:5': _Issue('proj', 5, 'summary-PROJ-5', 'Fixed'),
                   'other-project:13': _Issue('other-project', 13,
                                              'summary-OP-12', 'Invalid'),
                   'chromium:13': _Issue('chromium', 13,
                                         'summary-Cr-13', 'Invalid'),
                  }
    comp_ref_artifacts = (open_dict, closed_dict,)

    replacement_runs = autolink._ReplaceIssueRef(
        match, comp_ref_artifacts, single_issue_regex, default_project_name)
    return replacement_runs

  def testReplaceIssueRef_NoMatch(self):
    result = self.DoReplaceIssueRef('What is this all about?')
    self.assertIsNone(result)

  def testReplaceIssueRef_Normal(self):
    result = self.DoReplaceIssueRef(
        'This relates to issue 1', default_project_name='proj')
    self.assertEquals('/p/proj/issues/detail?id=1', result[0].href)
    self.assertEquals('issue 1', result[0].content)
    self.assertEquals(None, result[0].css_class)
    self.assertEquals('summary-PROJ-1', result[0].title)
    self.assertEquals('a', result[0].tag)

    result = self.DoReplaceIssueRef(
        ', issue #2', default_project_name='proj')
    self.assertEquals('/p/proj/issues/detail?id=2', result[0].href)
    self.assertEquals(' issue #2 ', result[0].content)
    self.assertEquals('closed_ref', result[0].css_class)
    self.assertEquals('summary-PROJ-2', result[0].title)
    self.assertEquals('a', result[0].tag)

    result = self.DoReplaceIssueRef(
        ', and issue3 ', default_project_name='proj')
    self.assertEquals(None, result[0].href)  # There is no issue 3
    self.assertEquals('issue3', result[0].content)

    result = self.DoReplaceIssueRef(
        'as well as bug 4', default_project_name='proj')
    self.assertEquals('/p/proj/issues/detail?id=4', result[0].href)
    self.assertEquals('bug 4', result[0].content)

    result = self.DoReplaceIssueRef(
        ', bug #5, ', default_project_name='proj')
    self.assertEquals('/p/proj/issues/detail?id=5', result[0].href)
    self.assertEquals(' bug #5 ', result[0].content)

    result = self.DoReplaceIssueRef(
        'and bug6', default_project_name='proj')
    self.assertEquals('/p/proj/issues/detail?id=6', result[0].href)
    self.assertEquals('bug6', result[0].content)

    result = self.DoReplaceIssueRef(
        'with issue other-project:12', default_project_name='proj')
    self.assertEquals('/p/other-project/issues/detail?id=12', result[0].href)
    self.assertEquals('issue other-project:12', result[0].content)

    result = self.DoReplaceIssueRef(
        'and issue other-project#13', default_project_name='proj')
    self.assertEquals('/p/other-project/issues/detail?id=13', result[0].href)
    self.assertEquals(' issue other-project#13 ', result[0].content)

  def testReplaceIssueRef_CrBug(self):
    result = self.DoReplaceIssueRef(
        'and crbug.com/other-project/13', regex=autolink._CRBUG_REF_RE,
        single_issue_regex=autolink._CRBUG_REF_RE,
        default_project_name='chromium')
    self.assertEquals('/p/other-project/issues/detail?id=13', result[0].href)
    self.assertEquals(' crbug.com/other-project/13 ', result[0].content)

    result = self.DoReplaceIssueRef(
        'and http://crbug.com/13', regex=autolink._CRBUG_REF_RE,
        single_issue_regex=autolink._CRBUG_REF_RE,
        default_project_name='chromium')
    self.assertEquals('/p/chromium/issues/detail?id=13', result[0].href)
    self.assertEquals(' http://crbug.com/13 ', result[0].content)

  def testParseProjectNameMatch(self):
    golden = 'project-name'
    variations = ['%s', '  %s', '%s  ', '%s:', '%s#', '%s#:', '%s:#', '%s :#',
                  '\t%s', '%s\t', '\t%s\t', '\t\t%s\t\t', '\n%s', '%s\n',
                  '\n%s\n', '\n\n%s\n\n', '\t\n%s', '\n\t%s', '%s\t\n',
                  '%s\n\t', '\t\n%s#', '\n\t%s#', '%s\t\n#', '%s\n\t#',
                  '\t\n%s:', '\n\t%s:', '%s\t\n:', '%s\n\t:'
                 ]

    # First pass checks all valid project name results
    for pattern in variations:
      self.assertEquals(
          golden, autolink._ParseProjectNameMatch(pattern % golden))

    # Second pass tests all inputs that should result in None
    for pattern in variations:
      self.assert_(
          autolink._ParseProjectNameMatch(pattern % '') in [None, ''])


class VCAutolinkTest(unittest.TestCase):

  GIT_HASH_1 = '1' * 40
  GIT_HASH_2 = '2' * 40
  GIT_HASH_3 = 'a1' * 20
  GIT_COMMENT_TEXT = (
      'This is a fix for r%s and R%s, by r2d2, who also authored revision %s, '
      'revision #%s, revision %s, and revision %s' % (
          GIT_HASH_1, GIT_HASH_2, GIT_HASH_3,
          GIT_HASH_1.upper(), GIT_HASH_2.upper(), GIT_HASH_3.upper()))
  SVN_COMMENT_TEXT = (
      'This is a fix for r12 and R34, by r2d2, who also authored revision r4, '
      'revision #1234567, revision 789, and revision 9025.  If you have '
      'questions, call me at 18005551212')

  def testGetReferencedRevisions(self):
    refs = ['1', '2', '3']
    # For now, we do not look up revision objects, result is always None
    self.assertIsNone(autolink.GetReferencedRevisions(None, refs))

  def testExtractGitHashes(self):
    refs = []
    for match in autolink._GIT_HASH_RE.finditer(self.GIT_COMMENT_TEXT):
      new_refs = autolink.ExtractRevNums(None, match)
      refs.extend(new_refs)

    self.assertEquals(
        refs, [self.GIT_HASH_1, self.GIT_HASH_2, self.GIT_HASH_3,
               self.GIT_HASH_1.upper(), self.GIT_HASH_2.upper(),
               self.GIT_HASH_3.upper()])

  def testExtractRevNums(self):
    refs = []
    for match in autolink._SVN_REF_RE.finditer(self.SVN_COMMENT_TEXT):
      new_refs = autolink.ExtractRevNums(None, match)
      refs.extend(new_refs)

    self.assertEquals(
        refs, ['12', '34', '4', '1234567', '789', '9025'])


  def DoReplaceRevisionRef(self, content, project=None):
    """Calls the ReplaceRevisionRef method and returns the result.

    Args:
      content: string with a hyperlink.
      project: optional project.

    Returns:
      A list of TextRuns with some runs will have the embedded URL hyperlinked.
      Or, None if no link was detected.
    """
    match = autolink._GIT_HASH_RE.search(content)
    if not match:
      return None

    mr = testing_helpers.MakeMonorailRequest(
        path='/p/proj/source/detail?r=1', project=project)
    replacement_runs = autolink.ReplaceRevisionRef(mr, match, None)
    return replacement_runs

  def testReplaceRevisionRef(self):
    result = self.DoReplaceRevisionRef(
        'This is a fix for r%s' % self.GIT_HASH_1)
    self.assertEquals('https://crrev.com/%s' % self.GIT_HASH_1, result[0].href)
    self.assertEquals('r%s' % self.GIT_HASH_1, result[0].content)

    result = self.DoReplaceRevisionRef(
        'and R%s, by r2d2, who ' % self.GIT_HASH_2)
    self.assertEquals('https://crrev.com/%s' % self.GIT_HASH_2, result[0].href)
    self.assertEquals('R%s' % self.GIT_HASH_2, result[0].content)

    result = self.DoReplaceRevisionRef('by r2d2, who ')
    self.assertEquals(None, result)

    result = self.DoReplaceRevisionRef(
        'also authored revision %s, ' % self.GIT_HASH_3)
    self.assertEquals('https://crrev.com/%s' % self.GIT_HASH_3, result[0].href)
    self.assertEquals('revision %s' % self.GIT_HASH_3, result[0].content)

    result = self.DoReplaceRevisionRef(
        'revision #%s, ' % self.GIT_HASH_1.upper())
    self.assertEquals(
        'https://crrev.com/%s' % self.GIT_HASH_1.upper(), result[0].href)
    self.assertEquals(
        'revision #%s' % self.GIT_HASH_1.upper(), result[0].content)

    result = self.DoReplaceRevisionRef(
        'revision %s, ' % self.GIT_HASH_2.upper())
    self.assertEquals(
        'https://crrev.com/%s' % self.GIT_HASH_2.upper(), result[0].href)
    self.assertEquals(
        'revision %s' % self.GIT_HASH_2.upper(), result[0].content)

    result = self.DoReplaceRevisionRef(
        'and revision %s' % self.GIT_HASH_3.upper())
    self.assertEquals(
        'https://crrev.com/%s' % self.GIT_HASH_3.upper(), result[0].href)
    self.assertEquals(
        'revision %s' % self.GIT_HASH_3.upper(), result[0].content)

  def testReplaceRevisionRef_CustomURL(self):
    """A project can override the URL used for revision links."""
    project = fake.Project()
    project.revision_url_format = 'http://example.com/+/{revnum}'
    result = self.DoReplaceRevisionRef(
        'This is a fix for r%s' % self.GIT_HASH_1, project=project)
    self.assertEquals(
        'http://example.com/+/%s' % self.GIT_HASH_1, result[0].href)
    self.assertEquals('r%s' % self.GIT_HASH_1, result[0].content)
