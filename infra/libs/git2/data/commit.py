# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import collections
import hashlib
import logging
import re

from cStringIO import StringIO

from infra.libs.decorators import cached_property
from infra.libs.infra_types import freeze

from infra.libs.git2.data.data import Alterable

LOGGER = logging.getLogger(__name__)


################################################################################
# Exceptions
################################################################################

class PartialCommit(Exception):
  def __init__(self, hsh, raw):
    super(PartialCommit, self).__init__(
        'Commit %s has partial content: %r' % (hsh, raw))
    self.raw = raw


class UnexpectedHeader(Exception):
  def __init__(self, hsh, header, value):
    super(UnexpectedHeader, self).__init__(
        'Unexpected header in commit %s: %r -> %r' % (hsh, header, value))


################################################################################
# Implementation
################################################################################

class CommitTimestamp(Alterable):
  def __init__(self, secs, sign, hours, mins):
    super(CommitTimestamp, self).__init__()
    assert isinstance(secs, int)
    assert sign in '+-'
    assert 0 <= hours < 24
    assert 0 <= mins < 60

    self._secs = secs
    self._sign = sign
    self._hours = hours
    self._mins = mins

  # Comparison & Representation
  def __eq__(self, other):
    return (self is other) or (
        isinstance(other, CommitTimestamp) and (
            self.secs == other.secs and
            self.sign == other.sign and
            self.hours == other.hours and
            self.mins == other.mins
        )
    )

  def __ne__(self, other):
    return not (self == other)

  def __repr__(self):
    return 'CommitTimestamp(%r, %r, %r, %r)' % (
        self.secs, self.sign, self.hours, self.mins)

  def __str__(self):
    return '%s %s' % (self.secs, self.tz_str)

  # Accessors
  # pylint: disable=W0212
  hours = property(lambda self: self._hours)
  mins = property(lambda self: self._mins)
  secs = property(lambda self: self._secs)
  sign = property(lambda self: self._sign)

  @property
  def tz_str(self):
    return '%s%02d%02d' % (self.sign, self.hours, self.mins)

  # Methods
  def to_dict(self):
    return {k: getattr(self, k) for k in ['secs', 'sign', 'hours', 'mins']}

  def alter(self, **kwargs):
    new_args = self.to_dict()
    assert set(new_args).issuperset(kwargs.keys())
    new_args.update(kwargs)
    return CommitTimestamp(**new_args)

  @classmethod
  def from_raw(cls, data):
    # \d+ [+-]HHMM
    secs, tz = data.split(' ')
    return cls(int(secs), tz[0], int(tz[1:3]), int(tz[3:5]))


NULL_TIMESTAMP = CommitTimestamp(0, '+', 0, 0)


class CommitUser(Alterable):
  def __init__(self, user, email, timestamp):
    super(CommitUser, self).__init__()
    assert isinstance(user, basestring) and user
    assert isinstance(email, basestring) and email
    assert isinstance(timestamp, CommitTimestamp)
    self._user = user
    self._email = email
    self._timestamp = timestamp

  # Comparison & Representation
  def __eq__(self, other):
    return (self is other) or (
        isinstance(other, CommitUser) and (
            self.user == other.user and
            self.email == other.email and
            self.timestamp == other.timestamp
        )
    )

  def __ne__(self, other):
    return not (self == other)

  def __repr__(self):
    return 'CommitUser(%r, %r, %r)' % (self.user, self.email, self.timestamp)

  def __str__(self):
    return '%s <%s> %s' % (self.user, self.email, self.timestamp)

  # Accessors
  # pylint: disable=W0212
  user = property(lambda self: self._user)
  email = property(lambda self: self._email)
  timestamp = property(lambda self: self._timestamp)

  # Methods
  def to_dict(self):
    return {k: getattr(self, k) for k in ['user', 'email', 'timestamp']}

  def alter(self, **kwargs):
    new_args = self.to_dict()
    assert set(new_args).issuperset(kwargs.keys())
    new_args.update(kwargs)
    return CommitUser(**new_args)

  @classmethod
  def from_raw(cls, data):
    # safe_string() ' <' safe_string() '> ' [TIMESTAMP]
    user, rest = data.split(' <', 1)
    email, rest = rest.split('> ', 1)
    return cls(user, email, CommitTimestamp.from_raw(rest))


class CommitData(Alterable):
  """A workable data representation of a git commit object.

  Knows how to parse all the standard fields of a git commit object:
    * tree
    * parent(s)
    * author
    * committer
    * commit message

  Also knows how to parse 'footers' which are an informally-defined mechanism to
  append key-value pairs to the ends of commit messages.

  Footers are stored internally as a list of (key, value) pairs. This is in
  order to provide full round-trip compatibility for CommitData, since footers
  have no implied ordering, other than the ordering in the commit. Consider the
  footers:

    A: 1
    B: 2
    A: 3

  In order to represent this as something better than a list which maintains the
  round-trip invariant, we would need a (Frozen)OrderedMultiDict, which would be
  tricky to implement.

  Author and committer are treated as the format defined by CommitUser
  """
  FOOTER_RE = re.compile(r'([-a-zA-Z]+): (.*)')
  HASH_RE = re.compile(r'[0-9a-f]{40}')

  def __init__(self, tree, parents, author, committer, other_header_lines,
               message_lines, footer_lines, no_trailing_nl):
    super(CommitData, self).__init__()
    assert all('\n' not in h and self.HASH_RE.match(h) for h in parents)
    assert tree is None or '\n' not in tree and self.HASH_RE.match(tree)
    assert isinstance(author, CommitUser)
    assert isinstance(committer, CommitUser)
    assert all(isinstance(l, str) for l in message_lines)
    assert all(len(i) == 2 and all(isinstance(x, str) for x in i)
               for i in other_header_lines)
    assert all(len(i) == 2 and all(isinstance(x, str) for x in i)
               for i in footer_lines)

    self._parents = freeze(parents)
    # default to the empty tree
    self._tree = tree or '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
    self._author = author
    self._committer = committer
    self._other_header_lines = freeze(other_header_lines)
    self._message_lines = freeze(message_lines)
    self._footer_lines = freeze(footer_lines)
    self._no_trailing_nl = no_trailing_nl

  # Comparison & Representation
  def __eq__(self, other):
    return (self is other) or (
        isinstance(other, CommitData) and (
            self.hsh == other.hsh
        )
    )

  def __ne__(self, other):
    return not (self == other)

  def __repr__(self):
    return (
        'CommitData({tree!r}, {parents!r}, {author!r}, {committer!r}, '
        '{other_header_lines!r}, {message_lines!r}, {footer_lines!r}, '
        '{no_trailing_nl!r})'
    ).format(**self.to_dict())

  def __str__(self):
    """Produces a string representation of this CommitData suitable for
    consumption by `git hash-object`.
    """
    ret = StringIO()
    print >> ret, 'tree', self.tree
    for parent in self.parents:
      print >> ret, 'parent', parent
    print >> ret, 'author', self.author
    print >> ret, 'committer', self.committer
    for key, value in self.other_header_lines:
      print >> ret, key, value
    print >> ret
    print >> ret, '\n'.join(self.message_lines)
    if self.footer_lines:
      print >> ret
    for key, value in self.footer_lines:
      print >> ret, '%s: %s' % (key, value)
    v = ret.getvalue()
    if self.no_trailing_nl:
      v = v[:-1]
    return v

  # Accessors
  # pylint: disable=W0212
  author = property(lambda self: self._author)
  committer = property(lambda self: self._committer)
  footer_lines = property(lambda self: self._footer_lines)
  message_lines = property(lambda self: self._message_lines)
  other_header_lines = property(lambda self: self._other_header_lines)
  parents = property(lambda self: self._parents)
  tree = property(lambda self: self._tree)
  no_trailing_nl = property(lambda self: self._no_trailing_nl)

  @cached_property
  def footers(self):
    return self.frozen_dict_from_kv_pairs(self.footer_lines)

  @cached_property
  def other_headers(self):
    return self.frozen_dict_from_kv_pairs(self.other_header_lines)

  @cached_property
  def hsh(self):
    return hashlib.sha1(str(self)).hexdigest()

  # Methods
  def to_dict(self):
    return {
        k: getattr(self, k)
        for k in ['parents', 'tree', 'author', 'committer',
                  'other_header_lines', 'message_lines', 'footer_lines',
                  'no_trailing_nl']
    }

  def alter(self, **kwargs):
    """In addition to the normal fields on this class, you may also provide
    'footers' and 'other_headers' instead of 'footer_lines' and
    'other_header_lines' respectively.

    These are an OrderedDict, which will be merged into the existing *_lines
    as described by merge_lines.
    """
    new_args = self.to_dict()
    if 'footers' in kwargs:
      assert 'footer_lines' not in kwargs
      new_args['footer_lines'] = self.merge_lines(
          self.footer_lines, kwargs.pop('footers'))
    if 'other_headers' in kwargs:
      assert 'other_header_lines' not in kwargs
      new_args['other_header_lines'] = self.merge_lines(
          self.other_header_lines, kwargs.pop('other_headers'))
    assert set(new_args).issuperset(kwargs.keys())
    new_args.update(kwargs)
    return CommitData(**new_args)

  @staticmethod
  def merge_lines(old_lines, new_dict):
    """Produces new footer or other_header_lines given the old lines and the
    new dictionary.

    Preserves the order of |old_lines| as much as possible.

    Rules:
      * If a key is in new_dict, but the key is not in old_lines, the new
        lines are added at the end.
      * If a key is not in new_dict, it is passed through.
      * If a key is equal to None in new_dict, lines with that key are removed.
      * If a key is present in both, all entries in new_dict for that key are
        inserted at the location of the first line in old_lines for that key
        (and any other lines in old_lines with that key are removed).

    Args:
      old_lines - a sequence of (key, value) pairs
      new_dict - an OrderedDict of {key: [values]} or {key: None}
    """
    old_dict = collections.OrderedDict()
    for key, value in old_lines:
      old_dict.setdefault(key, []).append(value)

    old_keys = set(old_dict)

    del_keys = {k for k, v in new_dict.iteritems() if not v}
    new_keys = ({k for k, v in new_dict.iteritems() if v} | old_keys) - del_keys

    # delete keys
    new_lines = [(k, v) for k, v in old_lines if k in new_keys]

    for change_key in (new_keys & old_keys):
      insert_idx = None
      to_nuke = set()
      for i, (k, v) in enumerate(new_lines):
        if k == change_key:
          if insert_idx is None:
            insert_idx = i
          to_nuke.add(i)
      assert to_nuke  # because it's in old_keys
      new_lines = [(k, v) for i, (k, v) in enumerate(new_lines)
                   if i not in to_nuke]
      new_lines[insert_idx:insert_idx] = [
          (change_key, v)
          for v in new_dict.get(change_key, old_dict[change_key])
      ]

    for add_key in new_dict:  # Preserve sort order of new lines
      if add_key in old_keys or add_key in del_keys:
        continue
      new_lines.extend((add_key, v) for v in new_dict[add_key])

    return new_lines

  @classmethod
  def from_raw(cls, data):
    """Turns the raw output of `git cat-file commit` into a CommitData."""
    users = {}
    parents = []
    tree = None
    hsh_ref = []
    def hsh_fn():
      if not hsh_ref:
        hsh_ref.append(hashlib.sha1(data).hexdigest())
      return hsh_ref[0]

    # use slice since data may be empty
    no_trailing_nl = data[-1:] != '\n'

    i = 0
    raw_lines = data.splitlines()
    other_header_lines = []
    for line in raw_lines:
      if not line:
        break
      header, data = line.split(' ', 1)
      if header == 'parent':
        parents.append(data)
      elif header in ('author', 'committer'):
        if header in users:
          raise UnexpectedHeader(hsh_fn(), header, data)
        users[header] = CommitUser.from_raw(data)
      elif header == 'tree':
        if tree:
          raise UnexpectedHeader(hsh_fn(), header, data)
        tree = data
      else:
        LOGGER.warn('Unexpected header in git commit %r: %r -> %r',
                     hsh_fn(), header, data)
        other_header_lines.append((header, data))
      i += 1

    message_lines, footer_lines = cls.parse_raw_message(raw_lines[i+1:])

    if not tree or set(('author', 'committer')).difference(users.keys()):
      raise PartialCommit(hsh_fn(), data)

    return cls(tree, parents, users['author'], users['committer'],
               other_header_lines, message_lines, footer_lines, no_trailing_nl)

  @classmethod
  def parse_raw_message(cls, raw_message_lines):
    # footers are lines in the form:
    #   ...message...
    #   <empty line>
    #   foo: data
    #   bar: other data
    #   ...
    #
    # If no empty line is found, they're considered not to exist.
    # If one line in the footers doesn't match the 'key: value' format, none
    #   of the footers are considered to exist.
    message_lines = raw_message_lines
    footer_lines = []

    i = 0
    for line in reversed(raw_message_lines):
      if not line:
        message_lines = raw_message_lines[:-(i+1)]
        break

      m = cls.FOOTER_RE.match(line)
      if m:
        footer_lines.append((m.group(1), m.group(2)))
      else:
        if i:
          footer_lines = []
          LOGGER.warn('Malformed footers')
        break
      i += 1
    else:
      LOGGER.warn('Footers comprise entire message')
      message_lines = []

    footer_lines.reverse()

    return message_lines, footer_lines

  @staticmethod
  def frozen_dict_from_kv_pairs(kv_pairs):
    ret = collections.OrderedDict()
    for key, value in kv_pairs:
      ret.setdefault(key, []).append(value)
    return freeze(ret)
