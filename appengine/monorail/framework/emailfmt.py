# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Functions that format or parse email messages in Monorail.

Specifically, this module has the logic for generating various email
header lines that help match inbound and outbound email to the project
and artifact that generated it.
"""

import hmac
import logging
import re
import rfc822

from google.appengine.api import app_identity

import settings
from framework import framework_constants
from services import client_config_svc
from services import secrets_svc

# TODO(jrobbins): Parsing very large messages is slow, and we are not going
# to handle attachments at first, so there is no reason to consider large
# emails.
MAX_BODY_SIZE = 100 * 1024
MAX_HEADER_CHARS_CONSIDERED = 255



def IsBodyTooBigToParse(body):
  """Return True if the email message body is too big to process."""
  return len(body) > MAX_BODY_SIZE


def IsProjectAddressOnToLine(project_addr, to_addrs):
  """Return True if an email was explicitly sent directly to us."""
  return project_addr in to_addrs


def ParseEmailMessage(msg):
  """Parse the given MessageRouterMessage and return relevant fields.

  Args:
    msg: email.message.Message object for the email message sent to us.

  Returns:
    A tuple: from_addr, to_addrs, cc_addrs, references,
    incident_id, subject, body.
  """
  # Ignore messages that are probably not from humans, see:
  # http://google.com/search?q=precedence+bulk+junk
  precedence = msg.get('precedence', '')
  if precedence.lower() in ['bulk', 'junk']:
    logging.info('Precedence: %r indicates an autoresponder', precedence)
    return '', [], [], '', '', '', ''

  from_addrs = _ExtractAddrs(msg.get('from', ''))
  if from_addrs:
    from_addr = from_addrs[0]
  else:
    from_addr = ''

  to_addrs = _ExtractAddrs(msg.get('to', ''))
  cc_addrs = _ExtractAddrs(msg.get('cc', ''))

  in_reply_to = msg.get('in-reply-to', '')
  incident_id = msg.get('x-incident-id', '')
  references = msg.get('references', '').split()
  references = list({ref for ref in [in_reply_to] + references if ref})
  subject = _StripSubjectPrefixes(msg.get('subject', ''))

  body = u''
  for part in msg.walk():
    # We only process plain text emails.
    if part.get_content_type() == 'text/plain':
      body = part.get_payload(decode=True)
      if not isinstance(body, unicode):
        body = body.decode('utf-8')
      break  # Only consider the first text part.

  return (from_addr, to_addrs, cc_addrs, references, incident_id, subject,
          body)


def _ExtractAddrs(header_value):
  """Given a message header value, return email address found there."""
  friendly_addr_pairs = list(rfc822.AddressList(header_value))
  return [addr for _friendly, addr in friendly_addr_pairs]


def _StripSubjectPrefixes(subject):
  """Strip off any 'Re:', 'Fwd:', etc. subject line prefixes."""
  prefix = _FindSubjectPrefix(subject)
  while prefix:
    subject = subject[len(prefix):].strip()
    prefix = _FindSubjectPrefix(subject)

  return subject


def _FindSubjectPrefix(subject):
  """If the given subject starts with a prefix, return that prefix."""
  for prefix in ['re:', 'aw:', 'fwd:', 'fw:']:
    if subject.lower().startswith(prefix):
      return prefix

  return None


def MailDomain():
  """Return the domain name where this app can recieve email."""
  if settings.unit_test_mode:
    return 'testbed-test.appspotmail.com'

  # If running on a GAFYD domain, you must define an app alias on the
  # Application Settings admin web page.  If you cannot reserve the matching
  # APP_ID for the alias, then specify it in settings.mail_domain.
  if settings.mail_domain:
    return settings.mail_domain

  app_id = app_identity.get_application_id()
  if ':' in app_id:
    app_id = app_id.split(':')[-1]

  return '%s.appspotmail.com' % app_id


def FormatFriendly(commenter_view, sender, reveal_addr):
  """Format the From: line to include the commenter's friendly name if given."""
  if commenter_view:
    site_name = settings.site_name.lower()
    if commenter_view.email in client_config_svc.GetServiceAccountMap():
      friendly = commenter_view.display_name
    elif reveal_addr:
      friendly = commenter_view.email
    else:
      friendly = u'%s\u2026@%s' % (
          commenter_view.obscured_username, commenter_view.domain)
    if '@' in sender:
      sender_username, sender_domain = sender.split('@', 1)
      sender = '%s+v2.%d@%s' % (
          sender_username, commenter_view.user_id, sender_domain)
      friendly = friendly.split('@')[0]
    return '%s via %s <%s>' % (friendly, site_name, sender)
  else:
    return sender


def NoReplyAddress(commenter_view=None, reveal_addr=False):
  """Return an address that ignores all messages sent to it."""
  # Note: We use "no_reply" with an underscore to avoid potential conflict
  # with any project name.  Project names cannot have underscores.
  sender = 'no_reply@%s' % MailDomain()
  return FormatFriendly(commenter_view, sender, reveal_addr)


def FormatFromAddr(_project, commenter_view=None, reveal_addr=False,
                   can_reply_to=True):
  """Return a string to be used on the email From: line.

  Args:
    project: Project PB for the project that the email is sent from.
    commenter_view: Optional UserView of the user who made a comment.  We use
        the user's (potentially obscured) email address as their friendly name.
    reveal_addr: Optional bool. If False then the address is obscured.
    can_reply_to: Optional bool. If True then settings.send_email_as is used,
        otherwise settings.send_noreply_email_as is used.

  Returns:
    A string that should be used in the From: line of outbound email
    notifications for the given project.
  """
  addr = (settings.send_email_as if can_reply_to
                                 else settings.send_noreply_email_as)
   # TODO(jrobbins): try this on just /p/monorail, then do full launch.
  return FormatFriendly(commenter_view, addr, reveal_addr)


def NormalizeHeader(s):
  """Make our message-ids robust against mail client spacing and truncation."""
  words = _StripSubjectPrefixes(s).split()  # Split on any runs of whitespace.
  normalized = ' '.join(words)
  truncated = normalized[:MAX_HEADER_CHARS_CONSIDERED]
  return truncated


def MakeMessageID(to_addr, subject, from_addr):
  """Make a unique (but deterministic) email Message-Id: value."""
  normalized_subject = NormalizeHeader(subject)
  if isinstance(normalized_subject, unicode):
    normalized_subject = normalized_subject.encode('utf-8')
  mail_hmac_key = secrets_svc.GetEmailKey()
  return '<0=%s=%s=%s@%s>' % (
      hmac.new(mail_hmac_key, to_addr).hexdigest(),
      hmac.new(mail_hmac_key, normalized_subject).hexdigest(),
      from_addr.split('@')[0],
      MailDomain())


def GetReferences(to_addr, subject, seq_num, project_from_addr):
  """Make a References: header to make this message thread properly.

  Args:
    to_addr: address that email message will be sent to.
    subject: subject line of email message.
    seq_num: sequence number of message in thread, e.g., 0, 1, 2, ...,
        or None if the message is not part of a thread.
    project_from_addr: address that the message will be sent from.

  Returns:
    A string Message-ID that does not correspond to any actual email
    message that was ever sent, but it does serve to unite all the
    messages that belong togther in a thread.
  """
  if seq_num is not None:
    return MakeMessageID(to_addr, subject, project_from_addr)
  else:
    return ''


def ValidateReferencesHeader(message_ref, project, from_addr, subject):
  """Check that the References header is one that we could have sent.

  Args:
    message_ref: one of the References header values from the inbound email.
    project: Project PB for the affected project.
    from_addr: string email address that inbound email was sent from.
    subject: string base subject line of inbound email.

  Returns:
    True if it looks like this is a reply to a message that we sent
    to the same address that replied.  Otherwise, False.
  """
  sender = '%s@%s' % (project.project_name, MailDomain())
  expected_ref = MakeMessageID(from_addr, subject, sender)

  # TODO(jrobbins): project option to not check from_addr.
  # TODO(jrobbins): project inbound auth token.
  return expected_ref == message_ref


PROJECT_EMAIL_RE = re.compile(
    r'(?P<project>[-a-z0-9]+)'
    r'(\+(?P<verb>[a-z0-9]+))?'
    r'@(?P<domain>[-a-z0-9.]+)')

ISSUE_CHANGE_SUBJECT_RE = re.compile(
    r'Issue (?P<local_id>[0-9]+) in '
    r'(?P<project>[-a-z0-9]+): '
    r'(?P<summary>.+)')

ISSUE_CHANGE_COMPACT_SUBJECT_RE = re.compile(
    r'(?P<project>[-a-z0-9]+):'
    r'(?P<local_id>[0-9]+): '
    r'(?P<summary>.+)')


def IdentifyIssue(project_name, subject):
  """Parse the artifact id from a reply and verify it is a valid issue.

  Args:
    project_name: string the project to search for the issue in.
    subject: string email subject line received, it must match the one
        sent.  Leading prefixes like "Re:" should already have been stripped.

  Returns:
    An int local_id for the id of the issue. None if no id is found or the id
    is not valid.
  """

  issue_project_name, local_id_str = _MatchSubject(subject)

  if project_name != issue_project_name:
    # Something is wrong with the project name.
    return None

  logging.info('project_name = %r', project_name)
  logging.info('local_id_str = %r', local_id_str)

  try:
    local_id = int(local_id_str)
  except (ValueError, TypeError):
    local_id = None

  return local_id


def IdentifyProjectAndVerb(project_addr):
    # Ignore any inbound email sent to a "no_reply@" address.
    if project_addr.startswith('no_reply@'):
      return None, None

    project_name = None
    verb = None
    m = PROJECT_EMAIL_RE.match(project_addr.lower())
    if m:
      project_name = m.group('project')
      verb = m.group('verb')

    return project_name, verb


def _MatchSubject(subject):
  """Parse the project, artifact type, and artifact id from a subject line."""
  m = (ISSUE_CHANGE_SUBJECT_RE.match(subject) or
       ISSUE_CHANGE_COMPACT_SUBJECT_RE.match(subject))
  if m:
    return m.group('project'), m.group('local_id')

  return None, None


# TODO(jrobbins): For now, we strip out lines that look like quoted
# text and then will give the user the option to see the whole email.
# For 2.0 of this feature, we should change the Comment PB to have
# runs of text with different properties so that the UI can present
# "- Show quoted text -" and expand it in-line.

# TODO(jrobbins): For now, we look for lines that indicate quoted
# text (e.g., they start with ">").  But, we should also collapse
# multiple lines that are identical to other lines in previous
# non-deleted comments on the same issue, regardless of quote markers.


# We cut off the message if we see something that looks like a signature and
# it is near the bottom of the message.
SIGNATURE_BOUNDARY_RE = re.compile(
    r'^(([-_=]+ ?)+|'
    r'cheers|(best |warm |kind )?regards|thx|thanks|thank you|'
    r'Sent from my i?Phone|Sent from my iPod)'
    r',? *$', re.I)

MAX_SIGNATURE_LINES = 8

FORWARD_OR_EXPLICIT_SIG_PATS = [
  r'[^0-9a-z]+(forwarded|original) message[^0-9a-z]+\s*$',
  r'Updates:\s*$',
  r'Comment #\d+ on issue \d+ by \S+:',
  # If we see this anywhere in the message, treat the rest as a signature.
  r'--\s*$',
  ]
FORWARD_OR_EXPLICIT_SIG_PATS_AND_REST_RE = re.compile(
  r'^(%s)(.|\n)*' % '|'.join(FORWARD_OR_EXPLICIT_SIG_PATS),
  flags=re.MULTILINE | re.IGNORECASE)

# This handles gmail well, and it's pretty broad without seeming like
# it would cause false positives.
QUOTE_PATS = [
  r'^On .*\s+<\s*\S+?@[-a-z0-9.]+>\s*wrote:\s*$',
  r'^On .* \S+?@[-a-z0-9.]+\s*wrote:\s*$',
  r'^\S+?@[-a-z0-9.]+ \(\S+?@[-a-z0-9.]+\)\s*wrote:\s*$',
  r'\S+?@[-a-z0-9]+.appspotmail.com\s.*wrote:\s*$',
  r'\S+?@[-a-z0-9]+.appspotmail.com\s+.*a\s+\xc3\xa9crit\s*:\s*$',
  r'^\d+/\d+/\d+ +<\S+@[-a-z0-9.]+>:?\s*$',
  r'^>.*$',
  ]
QUOTED_BLOCKS_RE = re.compile(
  r'(^\s*\n)*((%s)\n?)+(^\s*\n)*' % '|'.join(QUOTE_PATS),
  flags=re.MULTILINE | re.IGNORECASE)


def StripQuotedText(description):
  """Strip all quoted text lines out of the given comment text."""
  # If the rest of message is forwared text, we're done.
  description = FORWARD_OR_EXPLICIT_SIG_PATS_AND_REST_RE.sub('', description)
  # Replace each quoted block of lines and surrounding blank lines with at
  # most one blank line.
  description = QUOTED_BLOCKS_RE.sub('\n', description)

  new_lines = description.strip().split('\n')
  # Make another pass over the last few lines to strip out signatures.
  sig_zone_start = max(0, len(new_lines) - MAX_SIGNATURE_LINES)
  for idx in range(sig_zone_start, len(new_lines)):
    line = new_lines[idx]
    if SIGNATURE_BOUNDARY_RE.match(line):
      # We found the likely start of a signature, just keep the lines above it.
      new_lines = new_lines[:idx]
      break

  return '\n'.join(new_lines).strip()
