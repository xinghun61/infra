# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from app.framework.response import failure, abort


class DefaultRootModel(ndb.Model):
  def __init__(self, *args, **kwargs):
    kwargs['parent'] = (kwargs.get('parent') or
                        kwargs.get('scheduler') or
                        self._default_root)
    super(DefaultRootModel, self).__init__(*args, **kwargs)

  @classmethod
  def query(cls, *args, **kwargs):
    kwargs['ancestor'] = (kwargs.get('ancestor') or
                          kwargs.get('scheduler') or
                          cls._default_root)
    return super(DefaultRootModel, cls).query(*args, **kwargs)

  @classmethod
  def get_by_id(cls, *args, **kwargs):
    kwargs['parent'] = (kwargs.get('parent') or
                        kwargs.get('scheduler') or
                        cls._default_root)
    return super(DefaultRootModel, cls).get_by_id(*args, **kwargs)

  @classmethod
  def get_by_id_or_abort(cls, *args, **kwargs):
    res = cls.get_by_id(*args, **kwargs)
    if res is None:
      abort('%s not found' % cls.__name__)
    return res

  def to_dict(self):
    dct = super(DefaultRootModel, self).to_dict()
    dct['id'] = self.key.id()
    return dct
