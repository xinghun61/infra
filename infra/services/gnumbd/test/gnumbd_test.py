# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import sys

from cStringIO import StringIO

import expect_tests

from infra.libs import infra_types
from infra.libs.git2.testing_support import TestClock
from infra.libs.git2.testing_support import TestRepo
from infra.services.gnumbd import gnumbd
from infra.services.gnumbd.test import gnumbd_test_definitions


BASE_PATH = os.path.dirname(os.path.abspath(__file__))


class TestConfigRef(gnumbd.GnumbdConfigRef):
  def update(self, **values):
    new_config = self.current
    new_config.update(values)
    self.ref.make_commit(
        'update(%r)' % values.keys(),
        {'config.json': json.dumps(new_config)})


def RunTest(test_name):
  ret = []
  clock = TestClock()
  origin = TestRepo('origin', clock)
  local = TestRepo('local', clock, origin.repo_path)

  cref = TestConfigRef(origin)
  cref.update(enabled_refglobs=['refs/heads/*'], interval=0)

  def checkpoint(message, include_committer=False, include_config=False):
    ret.append([message, {'origin': origin.snap(include_committer,
                                                include_config)}])

  def run(include_log=True):
    stdout = sys.stdout
    stderr = sys.stderr

    if include_log:
      logout = StringIO()
      root_logger = logging.getLogger()
      log_level = root_logger.getEffectiveLevel()
      shandler = logging.StreamHandler(logout)
      shandler.setFormatter(
          logging.Formatter('%(levelname)s: %(message)s'))
      root_logger.addHandler(shandler)
      root_logger.setLevel(logging.INFO)

    success = False
    synthesized_commits = []
    try:
      sys.stderr = sys.stdout = open(os.devnull, 'w')
      local.reify()
      success, synthesized_commits = gnumbd.inner_loop(local, cref, clock)
    except Exception:  # pragma: no cover
      import traceback
      ret.append(traceback.format_exc().splitlines())
    finally:
      sys.stdout = stdout
      sys.stderr = stderr

      if include_log:
        root_logger.removeHandler(shandler)
        root_logger.setLevel(log_level)
        ret.append({'log output': logout.getvalue().splitlines()})

      ret.append({
        'inner_loop success': success,
        'synthesized_commits': [
          {
            'commit': c.hsh,
            'footers': infra_types.thaw(c.data.footers),
          } for c in synthesized_commits
        ],
      })

  gnumbd_test_definitions.GNUMBD_TESTS[test_name](
      origin, local, cref, run, checkpoint)

  return expect_tests.Result(ret)


@expect_tests.test_generator
def GenTests():
  for test_name, test in gnumbd_test_definitions.GNUMBD_TESTS.iteritems():
    yield expect_tests.Test(
        __package__ + '.' + test_name,
        expect_tests.FuncCall(RunTest, test_name),
        expect_base=test_name, ext='yaml', break_funcs=[test],
        covers=(
            expect_tests.Test.covers_obj(RunTest) +
            expect_tests.Test.covers_obj(gnumbd_test_definitions)
        ))
