# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for monorail.framework.emailfmt."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest

from google.appengine.ext import testbed

import settings
from framework import emailfmt
from framework import framework_views
from proto import project_pb2
from testing import testing_helpers

from google.appengine.api import apiproxy_stub_map


class EmailFmtTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def testValidateReferencesHeader(self):
    project = project_pb2.Project()
    project.project_name = 'open-open'
    subject = 'slipped disk'
    expected = emailfmt.MakeMessageID(
        'jrobbins@gmail.com', subject,
        '%s@%s' % (project.project_name, emailfmt.MailDomain()))
    self.assertTrue(
        emailfmt.ValidateReferencesHeader(
            expected, project, 'jrobbins@gmail.com', subject))

    self.assertFalse(
        emailfmt.ValidateReferencesHeader(
            expected, project, 'jrobbins@gmail.com', 'something else'))

    self.assertFalse(
        emailfmt.ValidateReferencesHeader(
            expected, project, 'someoneelse@gmail.com', subject))

    project.project_name = 'other-project'
    self.assertFalse(
        emailfmt.ValidateReferencesHeader(
            expected, project, 'jrobbins@gmail.com', subject))

  def testParseEmailMessage(self):
    msg = testing_helpers.MakeMessage(testing_helpers.HEADER_LINES, 'awesome!')

    (from_addr, to_addrs, cc_addrs, references, incident_id,
     subject, body) = emailfmt.ParseEmailMessage(msg)

    self.assertEqual('user@example.com', from_addr)
    self.assertEqual(['proj@monorail.example.com'], to_addrs)
    self.assertEqual(['ningerso@chromium.org'], cc_addrs)
    # Expected msg-id was generated from a previous known-good test run.
    self.assertEqual(['<0=969704940193871313=13442892928193434663='
                      'proj@monorail.example.com>'],
                     references)
    self.assertEqual('', incident_id)
    self.assertEqual('Issue 123 in proj: broken link', subject)
    self.assertEqual('awesome!', body)

    references_header = ('References', '<1234@foo.com> <5678@bar.com>')
    msg = testing_helpers.MakeMessage(
        testing_helpers.HEADER_LINES + [references_header], 'awesome!')
    (from_addr, to_addrs, cc_addrs, references, incident_id, subject,
     body) = emailfmt.ParseEmailMessage(msg)
    self.assertItemsEqual(
        ['<5678@bar.com>',
         '<0=969704940193871313=13442892928193434663='
         'proj@monorail.example.com>',
         '<1234@foo.com>'],
        references)

  def testParseEmailMessage_Bulk(self):
    for precedence in ['Bulk', 'Junk']:
      msg = testing_helpers.MakeMessage(
          testing_helpers.HEADER_LINES + [('Precedence', precedence)],
          'I am on vacation!')

      (from_addr, to_addrs, cc_addrs, references, incident_id, subject,
       body) = emailfmt.ParseEmailMessage(msg)

      self.assertEqual('', from_addr)
      self.assertEqual([], to_addrs)
      self.assertEqual([], cc_addrs)
      self.assertEqual('', references)
      self.assertEqual('', incident_id)
      self.assertEqual('', subject)
      self.assertEqual('', body)

  def testExtractAddrs(self):
    header_val = ''
    self.assertEqual(
        [], emailfmt._ExtractAddrs(header_val))

    header_val = 'J. Robbins <a@b.com>, c@d.com,\n Nick "Name" Dude <e@f.com>'
    self.assertEqual(
        ['a@b.com', 'c@d.com', 'e@f.com'],
        emailfmt._ExtractAddrs(header_val))

    header_val = ('hot: J. O\'Robbins <a@b.com>; '
                  'cool: "friendly" <e.g-h@i-j.k-L.com>')
    self.assertEqual(
        ['a@b.com', 'e.g-h@i-j.k-L.com'],
        emailfmt._ExtractAddrs(header_val))

  def CheckIdentifiedValues(
      self, project_addr, subject, expected_project_name, expected_local_id,
      expected_verb=None, expected_label=None):
    """Testing helper function to check 3 results against expected values."""
    project_name, verb, label = emailfmt.IdentifyProjectVerbAndLabel(
        project_addr)
    local_id = emailfmt.IdentifyIssue(project_name, subject)
    self.assertEqual(expected_project_name, project_name)
    self.assertEqual(expected_local_id, local_id)
    self.assertEqual(expected_verb, verb)
    self.assertEqual(expected_label, label)

  def testIdentifyProjectAndIssues_Normal(self):
    """Parse normal issue notification subject lines."""
    self.CheckIdentifiedValues(
        'proj@monorail.example.com',
        'Issue 123 in proj: the dogs wont eat the dogfood',
        'proj', 123)

    self.CheckIdentifiedValues(
        'Proj@MonoRail.Example.Com',
        'Issue 123 in proj: the dogs wont eat the dogfood',
        'proj', 123)

    self.CheckIdentifiedValues(
        'proj-4-u@test-example3.com',
        'Issue 123 in proj-4-u: this one goes to: 11',
        'proj-4-u', 123)

    self.CheckIdentifiedValues(
        'night@monorail.example.com',
        'Issue 451 in day: something is fishy',
        'night', None)

  def testIdentifyProjectAndIssues_Compact(self):
    """Parse compact subject lines."""
    self.CheckIdentifiedValues(
        'proj@monorail.example.com',
        'proj:123: the dogs wont eat the dogfood',
        'proj', 123)

    self.CheckIdentifiedValues(
        'Proj@MonoRail.Example.Com',
        'proj:123: the dogs wont eat the dogfood',
        'proj', 123)

    self.CheckIdentifiedValues(
        'proj-4-u@test-example3.com',
        'proj-4-u:123: this one goes to: 11',
        'proj-4-u', 123)

    self.CheckIdentifiedValues(
        'night@monorail.example.com',
        'day:451: something is fishy',
        'night', None)

  def testIdentifyProjectAndIssues_NotAMatch(self):
    """These subject lines do not match the ones we send."""
    self.CheckIdentifiedValues(
        'no_reply@chromium.org',
        'Issue 234 in project foo: ignore this one',
        None, None)

    self.CheckIdentifiedValues(
        'no_reply@chromium.org',
        'foo-234: ignore this one',
        None, None)

  def testStripSubjectPrefixes(self):
    self.assertEqual(
        '',
        emailfmt._StripSubjectPrefixes(''))

    self.assertEqual(
        'this is it',
        emailfmt._StripSubjectPrefixes('this is it'))

    self.assertEqual(
        'this is it',
        emailfmt._StripSubjectPrefixes('re: this is it'))

    self.assertEqual(
        'this is it',
        emailfmt._StripSubjectPrefixes('Re: Fwd: aw:this is it'))

    self.assertEqual(
        'This - . IS it',
        emailfmt._StripSubjectPrefixes('This - . IS it'))


class MailDomainTest(unittest.TestCase):

  def testTrivialCases(self):
    self.assertEqual(
        'testbed-test.appspotmail.com',
        emailfmt.MailDomain())


class NoReplyAddressTest(unittest.TestCase):

  def testNoCommenter(self):
    self.assertEqual(
        'no_reply@testbed-test.appspotmail.com',
        emailfmt.NoReplyAddress())

  def testWithCommenter(self):
    commenter_view = framework_views.StuffUserView(
        111, 'user@example.com', True)
    self.assertEqual(
        'user via monorail '
        '<no_reply+v2.111@testbed-test.appspotmail.com>',
        emailfmt.NoReplyAddress(
            commenter_view=commenter_view, reveal_addr=True))

  def testObscuredCommenter(self):
    commenter_view = framework_views.StuffUserView(
        111, 'user@example.com', True)
    self.assertEqual(
        u'u\u2026 via monorail '
        '<no_reply+v2.111@testbed-test.appspotmail.com>',
        emailfmt.NoReplyAddress(
            commenter_view=commenter_view, reveal_addr=False))


class FormatFromAddrTest(unittest.TestCase):

  def setUp(self):
    self.project = project_pb2.Project(project_name='monorail')
    self.old_send_email_as_format = settings.send_email_as_format
    settings.send_email_as_format = 'monorail@%(domain)s'
    self.old_send_noreply_email_as_format = (
        settings.send_noreply_email_as_format)
    settings.send_noreply_email_as_format = 'monorail+noreply@%(domain)s'

  def tearDown(self):
    self.old_send_email_as_format = settings.send_email_as_format
    self.old_send_noreply_email_as_format = (
        settings.send_noreply_email_as_format)

  def testNoCommenter(self):
    self.assertEqual('monorail@chromium.org',
                     emailfmt.FormatFromAddr(self.project))

  @mock.patch('settings.branded_domains',
              {'monorail': 'bugs.branded.com', '*': 'bugs.chromium.org'})
  def testNoCommenter_Branded(self):
    self.assertEqual('monorail@branded.com',
                     emailfmt.FormatFromAddr(self.project))

  def testNoCommenterWithNoReply(self):
    self.assertEqual('monorail+noreply@chromium.org',
                     emailfmt.FormatFromAddr(self.project, can_reply_to=False))

  @mock.patch('settings.branded_domains',
              {'monorail': 'bugs.branded.com', '*': 'bugs.chromium.org'})
  def testNoCommenterWithNoReply_Branded(self):
    self.assertEqual('monorail+noreply@branded.com',
                     emailfmt.FormatFromAddr(self.project, can_reply_to=False))

  def testWithCommenter(self):
    commenter_view = framework_views.StuffUserView(
        111, 'user@example.com', True)
    self.assertEqual(
        u'user via monorail <monorail+v2.111@chromium.org>',
        emailfmt.FormatFromAddr(
            self.project, commenter_view=commenter_view, reveal_addr=True))

  @mock.patch('settings.branded_domains',
              {'monorail': 'bugs.branded.com', '*': 'bugs.chromium.org'})
  def testWithCommenter_Branded(self):
    commenter_view = framework_views.StuffUserView(
        111, 'user@example.com', True)
    self.assertEqual(
        u'user via monorail <monorail+v2.111@branded.com>',
        emailfmt.FormatFromAddr(
            self.project, commenter_view=commenter_view, reveal_addr=True))

  def testObscuredCommenter(self):
    commenter_view = framework_views.StuffUserView(
        111, 'user@example.com', True)
    self.assertEqual(
        u'u\u2026 via monorail <monorail+v2.111@chromium.org>',
        emailfmt.FormatFromAddr(
            self.project, commenter_view=commenter_view, reveal_addr=False))

  def testServiceAccountCommenter(self):
    johndoe_bot = '123456789@developer.gserviceaccount.com'
    commenter_view = framework_views.StuffUserView(
        111, johndoe_bot, True)
    self.assertEqual(
        ('johndoe via monorail <monorail+v2.111@chromium.org>'),
        emailfmt.FormatFromAddr(
            self.project, commenter_view=commenter_view, reveal_addr=False))


class NormalizeHeaderWhitespaceTest(unittest.TestCase):

  def testTrivialCases(self):
    self.assertEqual(
        '',
        emailfmt.NormalizeHeader(''))

    self.assertEqual(
        '',
        emailfmt.NormalizeHeader(' \t\n'))

    self.assertEqual(
        'a',
        emailfmt.NormalizeHeader('a'))

    self.assertEqual(
        'a b',
        emailfmt.NormalizeHeader(' a  b '))

  def testLongSummary(self):
    big_string = 'x' * 500
    self.assertEqual(
        big_string[:emailfmt.MAX_HEADER_CHARS_CONSIDERED],
        emailfmt.NormalizeHeader(big_string))

    big_string = 'x y ' * 500
    self.assertEqual(
        big_string[:emailfmt.MAX_HEADER_CHARS_CONSIDERED],
        emailfmt.NormalizeHeader(big_string))

    big_string = 'x   ' * 100
    self.assertEqual(
        'x ' * 99 + 'x',
        emailfmt.NormalizeHeader(big_string))

  def testNormalCase(self):
    self.assertEqual(
        '[a] b: c d',
        emailfmt.NormalizeHeader('[a]  b:\tc\n\td'))


class MakeMessageIDTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def testMakeMessageIDTest(self):
    message_id = emailfmt.MakeMessageID(
        'to@to.com', 'subject', 'from@from.com')
    self.assertTrue(message_id.startswith('<0='))
    self.assertEqual('testbed-test.appspotmail.com>',
                     message_id.split('@')[-1])

    settings.mail_domain = None
    message_id = emailfmt.MakeMessageID(
        'to@to.com', 'subject', 'from@from.com')
    self.assertTrue(message_id.startswith('<0='))
    self.assertEqual('testbed-test.appspotmail.com>',
                     message_id.split('@')[-1])

    message_id = emailfmt.MakeMessageID(
        'to@to.com', 'subject', 'from@from.com')
    self.assertTrue(message_id.startswith('<0='))
    self.assertEqual('testbed-test.appspotmail.com>',
                     message_id.split('@')[-1])

    message_id_ws_1 = emailfmt.MakeMessageID(
        'to@to.com',
        'this is a very long subject that is sure to be wordwrapped by gmail',
        'from@from.com')
    message_id_ws_2 = emailfmt.MakeMessageID(
        'to@to.com',
        'this is a  very   long subject   that \n\tis sure to be '
        'wordwrapped \t\tby gmail',
        'from@from.com')
    self.assertEqual(message_id_ws_1, message_id_ws_2)


class GetReferencesTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def testNotPartOfThread(self):
    refs = emailfmt.GetReferences(
        'a@a.com', 'hi', None, emailfmt.NoReplyAddress())
    self.assertEqual(0, len(refs))

  def testAnywhereInThread(self):
    refs = emailfmt.GetReferences(
        'a@a.com', 'hi', 0, emailfmt.NoReplyAddress())
    self.assertTrue(len(refs))
    self.assertTrue(refs.startswith('<0='))


class StripQuotedTextTest(unittest.TestCase):

  def CheckExpected(self, expected_output, test_input):
    actual_output = emailfmt.StripQuotedText(test_input)
    self.assertEqual(expected_output, actual_output)

  def testAllNewText(self):
    self.CheckExpected('', '')
    self.CheckExpected('', '\n')
    self.CheckExpected('', '\n\n')
    self.CheckExpected('new', 'new')
    self.CheckExpected('new', '\nnew\n')
    self.CheckExpected('new\ntext', '\nnew\ntext\n')
    self.CheckExpected('new\n\ntext', '\nnew\n\ntext\n')

  def testQuotedLines(self):
    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         '> something you said\n'
         '> that took two lines'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         '> something you said\n'
         '> that took two lines'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('> something you said\n'
         '> that took two lines\n'
         'new\n'
         'text\n'
         '\n'))

    self.CheckExpected(
        ('newtext'),
        ('> something you said\n'
         '> that took two lines\n'
         'newtext'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'On Mon, Jan 1, 2023, So-and-so <so@and-so.com> Wrote:\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'On Mon, Jan 1, 2023, So-and-so <so@and-so.com> Wrote:\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'On Mon, Jan 1, 2023, user@example.com via Monorail\n'
         '<monorail@chromium.com> Wrote:\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'On Jan 14, 2016 6:19 AM, "user@example.com via Monorail" <\n'
         'monorail@chromium.com> Wrote:\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'On Jan 14, 2016 6:19 AM, "user@example.com via Monorail" <\n'
         'monorail@monorail-prod.appspotmail.com> wrote:\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'On Mon, Jan 1, 2023, So-and-so so@and-so.com wrote:\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'On Wed, Sep 8, 2010 at 6:56 PM, So =AND= <so@gmail.com>wrote:\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'On Mon, Jan 1, 2023, So-and-so <so@and-so.com> Wrote:\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'project-name@testbed-test.appspotmail.com wrote:\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'project-name@testbed-test.appspotmail.com a \xc3\xa9crit :\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         'project.domain.com@testbed-test.appspotmail.com a \xc3\xa9crit :\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         '2023/01/4 <so@and-so.com>\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new\n'
         '\n'
         'text'),
        ('new\n'
         '2023/01/4 <so-and@so.com>\n'
         '\n'
         '> something you said\n'
         '> > in response to some other junk\n'
         '\n'
         'text\n'))

  def testBoundaryLines(self):

    self.CheckExpected(
        ('new'),
        ('new\n'
         '---- forwarded message ======\n'
         '\n'
         'something you said\n'
         '> in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new'),
        ('new\n'
         '-----Original Message-----\n'
         '\n'
         'something you said\n'
         '> in response to some other junk\n'
         '\n'
         'text\n'))

    self.CheckExpected(
        ('new'),
        ('new\n'
         '\n'
         'Updates:\n'
         '\tStatus: Fixed\n'
         '\n'
         'notification text\n'))

    self.CheckExpected(
        ('new'),
        ('new\n'
         '\n'
         'Comment #1 on issue 9 by username: Is there ...'
         'notification text\n'))

  def testSignatures(self):

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '-- \n'
         'Name\n'
         'phone\n'
         'funny quote, or legal disclaimers\n'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '--\n'
         'Name\n'
         'phone\n'
         'funny quote, or legal disclaimers\n'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '--\n'
         'Name\n'
         'ginormous signature\n'
         'phone\n'
         'address\n'
         'address\n'
         'address\n'
         'homepage\n'
         'social network A\n'
         'social network B\n'
         'social network C\n'
         'funny quote\n'
         '4 lines about why email should be short\n'
         'legal disclaimers\n'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '_______________\n'
         'Name\n'
         'phone\n'
         'funny quote, or legal disclaimers\n'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         'Thanks,\n'
         'Name\n'
         '\n'
         '_______________\n'
         'Name\n'
         'phone\n'
         'funny quote, or legal disclaimers\n'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         'Thanks,\n'
         'Name'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         'Cheers,\n'
         'Name'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         'Regards\n'
         'Name'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         'best regards'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         'THX'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         'Thank you,\n'
         'Name'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         'Sent from my iPhone'))

    self.CheckExpected(
        ('new\n'
         'text'),
        ('new\n'
         'text\n'
         '\n'
         'Sent from my iPod'))
