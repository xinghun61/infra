# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of functions that integrate the GAE search index with Monorail."""

import collections
import datetime
import logging
import re
import time

from google.appengine.api import search

from services import fulltext_helpers

from proto import ast_pb2
from proto import tracker_pb2


# TODO(jrobbins): Consider re-implementing this whole file by using a
# BNF syntax specification and a parser generator or library.

# encodings
UTF8 = 'utf-8'

# Field types and operators
BOOL = tracker_pb2.FieldTypes.BOOL_TYPE
DATE = tracker_pb2.FieldTypes.DATE_TYPE
NUM = tracker_pb2.FieldTypes.INT_TYPE
TXT = tracker_pb2.FieldTypes.STR_TYPE

EQ = ast_pb2.QueryOp.EQ
NE = ast_pb2.QueryOp.NE
LT = ast_pb2.QueryOp.LT
GT = ast_pb2.QueryOp.GT
LE = ast_pb2.QueryOp.LE
GE = ast_pb2.QueryOp.GE
TEXT_HAS = ast_pb2.QueryOp.TEXT_HAS
NOT_TEXT_HAS = ast_pb2.QueryOp.NOT_TEXT_HAS
IS_DEFINED = ast_pb2.QueryOp.IS_DEFINED
IS_NOT_DEFINED = ast_pb2.QueryOp.IS_NOT_DEFINED
KEY_HAS = ast_pb2.QueryOp.KEY_HAS

# Mapping from user query comparison operators to our internal representation.
OPS = {
    ':': TEXT_HAS,
    '=': EQ,
    '!=': NE,
    '<': LT,
    '>': GT,
    '<=': LE,
    '>=': GE,
}

# When the query has a leading minus, switch the operator for its opposite.
NEGATED_OPS = {
    EQ: NE,
    NE: EQ,
    LT: GE,
    GT: LE,
    LE: GT,
    GE: LT,
    TEXT_HAS: NOT_TEXT_HAS,
    # IS_DEFINED is handled separately.
    }

# This is a partial regular expression that matches all of our comparison
# operators, such as =, 1=, >, and <.  Longer ones listed first so that the
# shorter ones don't cause premature matches.
OPS_PATTERN = '|'.join(
    map(re.escape, sorted(OPS.keys(), key=lambda op: -len(op))))

# This RE extracts search terms from a subquery string.
TERM_RE = re.compile(
    r'(-?"[^"]+")|'  # E.g., ["division by zero"]
    r'(\S+(%s)[^ "]+)|'  # E.g., [stars>10]
    r'(\w+(%s)"[^"]+")|'  # E.g., [summary:"memory leak"]
    r'(-?[._\*\w][-._\*\w]+)'  # E.g., [-workaround]
    % (OPS_PATTERN, OPS_PATTERN), flags=re.UNICODE)

# This RE is used to further decompose a comparison term into prefix, op, and
# value.  E.g., [stars>10] or [is:open] or [summary:"memory leak"].  The prefix
# can include a leading "-" to negate the comparison.
OP_RE = re.compile(
    r'^(?P<prefix>[-_\w]*?)'
    r'(?P<op>%s)'
    r'(?P<value>([-\w][-\*,./:<=>@\w]*|"[^"]+"))$' %
    OPS_PATTERN,
    flags=re.UNICODE)


# Predefined issue fields passed to the query parser.
_ISSUE_FIELDS_LIST = [
    (ast_pb2.ANY_FIELD, TXT),
    ('attachment', TXT),  # attachment file names
    ('attachments', NUM),  # number of attachment files
    ('blocked', BOOL),
    ('blockedon', TXT),
    ('blockedon_id', NUM),
    ('blocking', TXT),
    ('blocking_id', NUM),
    ('cc', TXT),
    ('cc_id', NUM),
    ('comment', TXT),
    ('commentby', TXT),
    ('commentby_id', NUM),
    ('component', TXT),
    ('component_id', NUM),
    ('description', TXT),
    ('id', NUM),
    ('is_spam', BOOL),
    ('label', TXT),
    ('label_id', NUM),
    ('mergedinto', NUM),
    ('mergedinto_id', NUM),
    ('open', BOOL),
    ('owner', TXT),
    ('ownerbouncing', BOOL),
    ('owner_id', NUM),
    ('project', TXT),
    ('reporter', TXT),
    ('reporter_id', NUM),
    ('spam', BOOL),
    ('stars', NUM),
    ('starredby', TXT),
    ('starredby_id', NUM),
    ('status', TXT),
    ('status_id', NUM),
    ('summary', TXT),
    ]

_DATE_FIELDS = (
    'closed',
    'modified',
    'opened',
    'ownermodified',
    'ownerlastvisit',
    'statusmodified',
    'componentmodified',
    )

# Add all _DATE_FIELDS to _ISSUE_FIELDS_LIST.
_ISSUE_FIELDS_LIST.extend((date_field, DATE) for date_field in _DATE_FIELDS)

_DATE_FIELD_SUFFIX_TO_OP = {
    '-after': '>',
    '-before': '<',
}

BUILTIN_ISSUE_FIELDS = {
    f_name: tracker_pb2.FieldDef(field_name=f_name, field_type=f_type)
    for f_name, f_type in _ISSUE_FIELDS_LIST}


def ParseUserQuery(
    query, scope, builtin_fields, harmonized_config, warnings=None,
    now=None):
  """Parse a user query and return a set of structure terms.

  Args:
    query: string with user's query.  E.g., 'Priority=High'.
    scope: string search terms that define the scope in which the
        query should be executed.  They are expressed in the same
        user query language.  E.g., adding the canned query.
    builtin_fields: dict {field_name: FieldDef(field_name, type)}
        mapping field names to FieldDef objects for built-in fields.
    harmonized_config: config for all the projects being searched.
        @@@ custom field name is not unique in cross project search.
         - custom_fields = {field_name: [fd, ...]}
         - query build needs to OR each possible interpretation
         - could be label in one project and field in another project.
        @@@ what about searching across all projects?
    warnings: optional list to accumulate warning messages.
    now: optional timestamp for tests, otherwise time.time() is used.

  Returns:
    A QueryAST with conjunctions (usually just one), where each has a list of
    Condition PBs with op, fields, str_values and int_values.  E.g., the query
    [priority=high leak OR stars>100] over open issues would return
    QueryAST(
      Conjunction(Condition(EQ, [open_fd], [], [1]),
                  Condition(EQ, [label_fd], ['priority-high'], []),
                  Condition(TEXT_HAS, any_field_fd, ['leak'], [])),
      Conjunction(Condition(EQ, [open_fd], [], [1]),
                  Condition(GT, [stars_fd], [], [100])))

  Raises:
    InvalidQueryError: If a problem was detected in the user's query.
  """
  if warnings is None:
    warnings = []
  if _HasParens(query):
    warnings.append('Parentheses are ignored in user queries.')

  if _HasParens(scope):
    warnings.append('Parentheses are ignored in saved queries.')

  # Convert the overall query into one or more OR'd subqueries.
  subqueries = query.split(' OR ')

  # Make a dictionary of all fields: built-in + custom in each project.
  combined_fields = collections.defaultdict(
      list, {field_name: [field_def]
             for field_name, field_def in builtin_fields.iteritems()})
  for fd in harmonized_config.field_defs:
    if fd.field_type != tracker_pb2.FieldTypes.ENUM_TYPE:
      # Only do non-enum fields because enums are stored as labels
      combined_fields[fd.field_name.lower()].append(fd)

  conjunctions = [
      _ParseConjunction(sq, scope, combined_fields, warnings, now=now)
      for sq in subqueries]
  logging.info('search warnings: %r', warnings)
  return ast_pb2.QueryAST(conjunctions=conjunctions)


def _HasParens(s):
  """Return True if there are parentheses in the given string."""
  # Monorail cannot handle parenthesized expressions, so we tell the
  # user that immediately.  Even inside a quoted string, the GAE search
  # engine will not handle parens in TEXT-type fields.
  return '(' in s or ')' in s


def _ParseConjunction(subquery, scope, fields, warnings, now=None):
  """Parse part of a user query into a Conjunction PB."""
  logging.info('Parsing sub query: %r in scope %r', subquery, scope)
  scoped_query = ('%s %s' % (scope, subquery)).lower()
  cond_strs = _ExtractConds(scoped_query, warnings)
  conds = [_ParseCond(cond_str, fields, warnings, now=now)
           for cond_str in cond_strs]
  conds = [cond for cond in conds if cond]
  return ast_pb2.Conjunction(conds=conds)


def _ParseCond(cond_str, fields, warnings, now=None):
  """Parse one user query condition string into a Condition PB."""
  op_match = OP_RE.match(cond_str)
  # Do not treat as key:value search terms if any of the special prefixes match.
  special_prefixes_match = any(
      cond_str.startswith(p) for p in fulltext_helpers.NON_OP_PREFIXES)
  if op_match and not special_prefixes_match:
    prefix = op_match.group('prefix')
    op = op_match.group('op')
    val = op_match.group('value')
    # Special case handling to continue to support old date query terms from
    # code.google.com. See monorail:151 for more details.
    if prefix.startswith(_DATE_FIELDS):
      for date_suffix in _DATE_FIELD_SUFFIX_TO_OP:
        if prefix.endswith(date_suffix):
          prefix = prefix.rstrip(date_suffix)
          op = _DATE_FIELD_SUFFIX_TO_OP[date_suffix]
    return _ParseStructuredTerm(prefix, op, val, fields, now=now)

  # Treat the cond as a full-text search term, which might be negated.
  if cond_str.startswith('-'):
    op = NOT_TEXT_HAS
    cond_str = cond_str[1:]
  else:
    op = TEXT_HAS

  # Construct a full-text Query object as a dry-run to validate that
  # the syntax is acceptable.
  try:
    _fts_query = search.Query(cond_str)
  except search.QueryError:
    warnings.append('Ignoring full-text term: %s' % cond_str)
    return None

  # Flag a potential user misunderstanding.
  if cond_str.lower() in ('and', 'or', 'not'):
    warnings.append(
        'The only supported boolean operator is OR (all capitals).')

  return ast_pb2.MakeCond(
      op, [BUILTIN_ISSUE_FIELDS[ast_pb2.ANY_FIELD]], [cond_str], [])


def _ParseStructuredTerm(prefix, op_str, value, fields, now=None):
  """Parse one user structured query term into an internal representation.

  Args:
    prefix: The query operator, usually a field name.  E.g., summary. It can
      also be special operators like "is" to test boolean fields.
    op_str: the comparison operator.  Usually ":" or "=", but can be any OPS.
    value: the value to compare against, e.g., term to find in that field.
    fields: dict {name_lower: [FieldDef, ...]} for built-in and custom fields.
    now: optional timestamp for tests, otherwise time.time() is used.

  Returns:
    A Condition PB.
  """
  unquoted_value = value.strip('"')
  # Quick-OR is a convenient way to write one condition that matches any one of
  # multiple values, like set membership.  E.g., [Priority=High,Critical].
  quick_or_vals = [v.strip() for v in unquoted_value.split(',')]

  op = OPS[op_str]
  negate = False
  if prefix.startswith('-'):
    negate = True
    op = NEGATED_OPS.get(op, op)
    prefix = prefix[1:]

  if prefix == 'is' and unquoted_value in [
      'open', 'blocked', 'spam', 'ownerbouncing']:
    return ast_pb2.MakeCond(
        NE if negate else EQ, fields[unquoted_value], [], [])

  # Search entries with or without any value in the specified field.
  if prefix == 'has':
    op = IS_NOT_DEFINED if negate else IS_DEFINED
    if unquoted_value in fields:  # Look for that field with any value.
      return ast_pb2.MakeCond(op, fields[unquoted_value], [], [])
    else:  # Look for any label with that prefix.
      return ast_pb2.MakeCond(op, fields['label'], [unquoted_value], [])

  if prefix in fields:  # search built-in and custom fields. E.g., summary.
    # Note: if first matching field is date-type, we assume they all are.
    # TODO(jrobbins): better handling for rare case where multiple projects
    # define the same custom field name, and one is a date and another is not.
    first_field = fields[prefix][0]
    if first_field.field_type == DATE:
      date_values = [_ParseDateValue(val, now=now) for val in quick_or_vals]
      return ast_pb2.MakeCond(op, fields[prefix], [], date_values)
    else:
      quick_or_ints = []
      for qov in quick_or_vals:
        try:
          quick_or_ints.append(int(qov))
        except ValueError:
          pass
      return ast_pb2.MakeCond(op, fields[prefix], quick_or_vals, quick_or_ints)

  # Since it is not a field, treat it as labels, E.g., Priority.
  quick_or_labels = ['%s-%s' % (prefix, v) for v in quick_or_vals]
  # Convert substring match to key-value match if user typed 'foo:bar'.
  if op == TEXT_HAS:
    op = KEY_HAS
  return ast_pb2.MakeCond(op, fields['label'], quick_or_labels, [])


def _ExtractConds(query, warnings):
  """Parse a query string into a list of individual condition strings.

  Args:
    query: UTF-8 encoded search query string.
    warnings: list to accumulate warning messages.

  Returns:
    A list of query condition strings.
  """
  # Convert to unicode then search for distinct terms.
  term_matches = TERM_RE.findall(query)

  terms = []
  for (phrase, word_label, _op1, phrase_label, _op2,
       word) in term_matches:
    # Case 1: Quoted phrases, e.g., ["hot dog"].
    if phrase_label or phrase:
      terms.append(phrase_label or phrase)

    # Case 2: Comparisons
    elif word_label:
      special_prefixes_match = any(
          word_label.startswith(p) for p in fulltext_helpers.NON_OP_PREFIXES)
      match = OP_RE.match(word_label)
      if match and not special_prefixes_match:
        label = match.group('prefix')
        op = match.group('op')
        word = match.group('value')
        terms.append('%s%s"%s"' % (label, op, word))
      else:
        # It looked like a key:value cond, but not exactly, so treat it
        # as fulltext search.  It is probably a tiny bit of source code.
        terms.append('"%s"' % word_label)

    # Case 3: Simple words.
    elif word:
      terms.append(word)

    else:  # pragma: no coverage
      warnings.append('Unparsable search term')

  return terms


def _ParseDateValue(val, now=None):
  """Convert the user-entered date into timestamp."""
  # Support timestamp value such as opened>1437671476
  try:
    return int(val)
  except ValueError:
    pass

  # TODO(jrobbins): future: take timezones into account.
  # TODO(jrobbins): for now, explain to users that "today" is
  # actually now: the current time, not 12:01am in their timezone.
  # In fact, it is not very useful because everything in the system
  # happened before the current time.
  if val == 'today':
    return _CalculatePastDate(0, now=now)
  elif val.startswith('today-'):
    try:
      days_ago = int(val.split('-')[1])
    except ValueError:
      raise InvalidQueryError('Could not parse date: ' + val)
    return _CalculatePastDate(days_ago, now=now)

  try:
    if '/' in val:
      year, month, day = [int(x) for x in val.split('/')]
    elif '-' in val:
      year, month, day = [int(x) for x in val.split('-')]
    else:
      raise InvalidQueryError('Could not parse date: ' + val)
  except ValueError:
    raise InvalidQueryError('Could not parse date: ' + val)

  try:
    return int(time.mktime(datetime.datetime(year, month, day).timetuple()))
  except ValueError:
    raise InvalidQueryError('Could not parse date: ' + val)


def _CalculatePastDate(days_ago, now=None):
  """Calculates the timestamp N days ago from now."""
  if now is None:
    now = int(time.time())
  ts = now - days_ago * 24 * 60 * 60
  return ts


def CheckSyntax(query, harmonized_config, warnings=None):
  """Parse the given query and report the first error or None."""
  try:
    ParseUserQuery(
        query, '', BUILTIN_ISSUE_FIELDS, harmonized_config, warnings=warnings)
  except InvalidQueryError as e:
    return e.message

  return None


class Error(Exception):
  """Base exception class for this package."""
  pass


class InvalidQueryError(Error):
  """Error raised when an invalid query is requested."""
  pass
