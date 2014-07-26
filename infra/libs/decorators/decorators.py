# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools


class cached_property(object):
  """Like @property, except that the result of get is cached on
  self.{'_' + fn.__name__}.

  NOTE: This implementation is not threadsafe.

  >>> class Test(object):
  ...  @cached_property
  ...  def foo(self):
  ...   print "hello"
  ...   return 10
  ...
  >>> t = Test()
  >>> t.foo
  hello
  10
  >>> t.foo
  10
  >>> t.foo = 20
  >>> t.foo
  20
  >>> del t.foo
  >>> t.foo
  hello
  10
  >>>
  """
  def __init__(self, fn):
    self.func = fn
    self._iname = "_" + fn.__name__
    functools.update_wrapper(self, fn)

  def __get__(self, inst, cls=None):
    if inst is None:
      return self
    if not hasattr(inst, self._iname):
      val = self.func(inst)
      # Some methods call out to another layer to calculate the value. This
      # higher layer will assign directly to the property, so we have to do
      # the extra hasattr here to determine if the value has been set as a side
      # effect of func()
      if not hasattr(inst, self._iname):
        setattr(inst, self._iname, val)
    return getattr(inst, self._iname)

  def __delete__(self, inst):
    assert inst is not None
    if hasattr(inst, self._iname):
      delattr(inst, self._iname)
