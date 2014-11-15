# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(pgervais): this file as no tests

from calendar import timegm
import os


DEV_SERVER = os.environ.get('SERVER_SOFTWARE', '').startswith('Development')
PRODUCTION = not DEV_SERVER


def datetime_to_timestamp(dt):  #pragma: no cover
  return float(timegm(dt.timetuple()))


class RegexIdMixin(object):  #pragma: no cover
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
      raise ValueError('Entity id does not match "%s" regex: "%s"' %
                       (cls.ID_REGEX.pattern, entity_id))

  def validate_key(self):
    self.validate_id(self.key.id() if self.key else '')

  def _pre_put_hook(self):
    super(RegexIdMixin, self)._pre_put_hook()
    self.validate_key()

  def get_key_component(self, index):
    self.validate_key()
    if self.key is None:
      return None
    match = self.ID_REGEX.match(self.key.id())
    assert match, 'The key was validated, but it does not match'
    return match.group(index + 1)
