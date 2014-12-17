# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class BadIdError(Exception):
  """Raised when Entity id is malformed."""


class RegexIdMixin(object):
  """RegexIdMixin enforces an entity id to match a regular expression.

  Can be mixed into an entity, like this:
    class MyEntity(ndb.Model, RegexIdMixin):
      ID_REGEX = re.compile('abc\d[5]')

  Attributes:
    ID_REGEX (re.RegexObject): entity id pattern. A class attribute, must be
      provided by the entity that mixes RegexIdMixin.
  """

  @classmethod
  def validate_id(cls, entity_id):
    assert cls.ID_REGEX is not None, 'ID_REGEX of %s is None' % cls.__name__
    if not cls.ID_REGEX.match(entity_id):
      raise BadIdError('Entity id does not match "%s" regex: "%s"' %
                       (cls.ID_REGEX.pattern, entity_id))

  def validate_key(self):
    entity_id = self.key.id() or '' if self.key else ''
    self.validate_id(entity_id)

  def get_key_component(self, index):
    try:
      self.validate_key()
    except BadIdError:
      return None
    match = self.ID_REGEX.match(self.key.id())
    assert match, 'The key was validated, but it does not match'
    return match.group(index + 1)
