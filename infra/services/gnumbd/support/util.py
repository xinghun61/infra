# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import collections
import operator

from cStringIO import StringIO


class CalledProcessError(Exception):
  """Almost like subprocess.CalledProcessError, but also captures stderr,
  and gives prettier error messages.
  """
  def __init__(self, returncode, cmd, stdout, stderr):
    super(CalledProcessError, self).__init__()
    self.returncode = returncode
    self.cmd = cmd
    self.stdout = stdout
    self.stderr = stderr

  def __str__(self):
    msg = StringIO()

    suffix = ':' if self.stderr or self.stdout else '.'
    print >> msg, (
        "Command %r returned non-zero exit status %d%s"
        % (self.cmd, self.returncode, suffix)
    )

    def indent_data(banner, data):
      print >> msg, banner, '=' * 40
      msg.writelines('  ' + l for l in data.splitlines(True))

    if self.stdout:
      indent_data('STDOUT', self.stdout)

    if self.stderr:
      if self.stdout:
        print >> msg
      indent_data('STDERR', self.stderr)

    r = msg.getvalue()
    if r[-1] != '\n':
      r += '\n'
    return r


class cached_property(object):
  """Like @property, except that the result of get is cached on
  self.{'_' + fn.__name__}.

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
    self.__name__ = fn.__name__
    self.__doc__ = fn.__doc__
    self.__module__ = fn.__module__

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


def freeze(obj):
  """Takes a jsonish object |obj|, and returns an immutable version of it."""
  if isinstance(obj, dict):
    return FrozenDict((freeze(k), freeze(v)) for k, v in obj.iteritems())
  elif isinstance(obj, list):
    return tuple(freeze(i) for i in obj)
  elif isinstance(obj, set):
    return frozenset(freeze(i) for i in obj)
  else:
    hash(obj)
    return obj


def thaw(obj):
  """Takes an object from freeze() and returns a mutable copy of it."""
  if isinstance(obj, FrozenDict):
    return collections.OrderedDict(
        (thaw(k), thaw(v)) for k, v in obj.iteritems())
  elif isinstance(obj, tuple):
    return list(thaw(i) for i in obj)
  elif isinstance(obj, frozenset):
    return set(thaw(i) for i in obj)
  else:
    return obj


class FrozenDict(collections.Mapping):
  """An immutable OrderedDict.

  Modified From: http://stackoverflow.com/a/2704866
  """
  def __init__(self, *args, **kwargs):
    self._d = collections.OrderedDict(*args, **kwargs)
    self._hash = reduce(operator.xor,
                        (hash(i) for i in enumerate(self._d.iteritems())), 0)

  def __eq__(self, other):
    if not isinstance(other, collections.Mapping):
      return NotImplemented
    if self is other:
      return True
    if len(self) != len(other):
      return False
    for k, v in self.iteritems():
      if k not in other or other[k] != v:
        return False
    return True

  def __iter__(self):
    return iter(self._d)

  def __len__(self):
    return len(self._d)

  def __getitem__(self, key):
    return self._d[key]

  def __hash__(self):
    return self._hash

  def __repr__(self):
    return 'FrozenDict(%r)' % (self._d.items(),)
