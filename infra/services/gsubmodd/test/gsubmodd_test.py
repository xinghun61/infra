# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import tempfile
import traceback
import sys

from cStringIO import StringIO

import expect_tests

from infra.libs.git2.testing_support import TestClock
from infra.libs.git2.testing_support import TestRepo
from infra.services.gsubmodd import gsubmodd
from infra.services.gsubmodd.test import gsubmodd_test_definitions


MASTER = 'refs/heads/master'


class Context(object):
  """Test fixture with pieces useful for most tests.

  This gets passed to each test script as an arg.  Typical usage:

      @test
      def test_name(f):  # `f` is the test "fixture"
        f.make_commit(...)  # construct a commit at the origin repo
        f.checkpoint('before')  # dump repo contents for expect output
        f.run()  # run the code under test
        f.checkpoint('after')  # dump modified repo content

  In special cases tests may customize the fixture before using it.
  """

  def __init__(self):
    self._clock = TestClock()
    self.results = []
    # The `origin` and `target` are initialized lazily, so that special
    # tests can customize them.
    self.origin = None
    self.local = None
    self.target = None
    self.target_url = None

  # pylint: disable=W0212
  actual_results = property(lambda self: self.results)

  def _ensure_init(self):
    """Performs lazy initialization."""
    if not self.origin:
      self._init_origin('fount')
    if not self.target:
      self._init_target()

  def _init_origin(self, name):
    self.origin = TestRepo(name, self._clock)
    self.local = TestRepo('local', self._clock, self.origin.repo_path)

  def _init_target(self):
    assert self.origin
    full_path = os.path.join(os.path.dirname(self.origin.repo_path), "grimoire")
    self.target_url = 'file://' + full_path
    os.makedirs(full_path)
    self.target = TestRepo('target', self._clock, '(ignored)')
    self.target._repo_path = full_path
    self.target.run('init', '--bare')

  def make_commit(self, description, spec):
    self._ensure_init()
    return self.origin[MASTER].make_commit(description, spec)

  def record(self, o):
    self.results.append(o)

  def run(self, **kwargs):
    self._ensure_init()
    stdout = sys.stdout
    stderr = sys.stderr

    class LogFilterer(logging.Filter):
      def filter(self, record):
        # infra.libs.git2.repo logs this message if the command took longer than
        # 1s to run.  This causes test flakes occasionally.
        if (record.name.startswith('infra.libs.git2.repo.Repo') and
            record.msg.startswith('Finished in ')):  # pragma: no cover
          return False

        return record.name.startswith((
          'infra.services.gsubmodd',
          'infra.libs.deps2submodules',
          'infra.libs.git2',
        ))

    logout = StringIO()
    root_logger = logging.getLogger()
    shandler = logging.StreamHandler(logout)
    shandler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    shandler.addFilter(LogFilterer())
    root_logger.addHandler(shandler)
    shandler.setLevel(logging.INFO)

    fd, filename = tempfile.mkstemp(text=True)
    try:
      with os.fdopen(fd, 'w+') as fh:
        sys.stderr = sys.stdout = fh
        try:
          self.local.reify()
          ret = gsubmodd.reify_submodules(self.local, self.target_url, **kwargs)
          if not ret:
            self.record('reify_submodules() call failed')
        except Exception:  # pragma: no cover
          self.record(traceback.format_exc().splitlines())
        fh.seek(0)
        # Uncomment temporarily when needed for debugging
        # self.record({'stdio':fh.read().splitlines()})
    except Exception:  # pragma: no cover
      self.record(traceback.format_exc().splitlines())
    finally:
      sys.stdout = stdout
      sys.stderr = stderr
      root_logger.removeHandler(shandler)
      self.record({'log output': logout.getvalue().splitlines()})
      os.remove(filename)

  def checkpoint(self, message, *args):
    self._ensure_init()
    self.record([message, _preserve_commit_order(self.origin.snap()),
                 _preserve_commit_order(self.target.snap())]
                + [arg for arg in args])


def _preserve_commit_order(ordered):
  return {k:v.items() for k,v in ordered.items()}


def RunTest(test_name):
  context = Context()
  gsubmodd_test_definitions.GSUBMODD_TESTS[test_name](context)
  return expect_tests.Result(context.actual_results)


@expect_tests.test_generator
def GenTests():
  for test_name, test in gsubmodd_test_definitions.GSUBMODD_TESTS.iteritems():
    yield expect_tests.Test(
        '%s.%s' % (__package__, test_name),
        expect_tests.FuncCall(RunTest, test_name),
        expect_base=test_name, break_funcs=[test],
        covers=(
            expect_tests.Test.covers_obj(RunTest) +
            expect_tests.Test.covers_obj(gsubmodd_test_definitions)))
