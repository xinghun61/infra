# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import logging
import os
import subprocess
import sys
import tempfile
import traceback

from cStringIO import StringIO

import expect_tests

from infra.libs.git2.testing_support import TestClock
from infra.libs.git2.testing_support import TestRepo
from infra.services.gsubtreed import gsubtreed
from infra.services.gsubtreed.test import gsubtreed_test_definitions


BASE_PATH = os.path.dirname(os.path.abspath(__file__))


class TestConfigRef(gsubtreed.GsubtreedConfigRef):
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

  base_repo_path = tempfile.mkdtemp()

  enabled_paths = ['mirrored_path/subpath', 'mirrored_path']
  cref = TestConfigRef(origin)
  cref.update(enabled_paths=enabled_paths, base_url='file://' + base_repo_path)

  for path in enabled_paths:
    full_path = os.path.join(base_repo_path, path)
    try:
      os.makedirs(full_path)
    except OSError:
      pass
    with open(os.devnull, 'w') as dn:
      subprocess.check_call(['git', 'init', '--bare'], cwd=full_path,
                            stdout=dn, stderr=dn)

  def checkpoint(message, include_committer=False, include_config=False):
    osnap = origin.snap(include_committer, include_config)
    for ref in osnap:
      # since the subtree-processed refs are actually tags on master, don't
      # bother showing them in their entirety
      if 'subtree-processed' in ref:
        if len(osnap[ref]) <= 1:
          continue  # pragma: no cover
        osnap[ref] = collections.OrderedDict([
          next(osnap[ref].iteritems()),
          ('etc', '...')
        ])
    ret.append([message, {'origin': osnap}])

  def run():
    stdout = sys.stdout
    stderr = sys.stderr

    logout = StringIO()
    root_logger = logging.getLogger()
    shandler = logging.StreamHandler(logout)
    shandler.setFormatter(
        logging.Formatter('%(levelname)s: %(message)s'))
    root_logger.addHandler(shandler)
    shandler.setLevel(logging.INFO)

    # Run pusher threads sequentially and deterministically.
    gsubtreed.Pusher.FAKE_THREADING = True

    success = False
    processed = {}
    try:
      with open(os.devnull, 'w') as dn:
        # TODO(iannucci): Let expect_tests absorb stdio
        sys.stderr = sys.stdout = dn
        local.reify()
        success, processed = gsubtreed.inner_loop(local, cref)
    except Exception:  # pragma: no cover
      ret.append(traceback.format_exc().splitlines())
    finally:
      gsubtreed.Pusher.FAKE_THREADING = False

      sys.stdout = stdout
      sys.stderr = stderr

      root_logger.removeHandler(shandler)
      ret.append({'log output': logout.getvalue().splitlines()})

      ret.append({
        'inner_loop success': success,
        'processed': processed,
      })

  gsubtreed_test_definitions.GSUBTREED_TESTS[test_name](origin, run, checkpoint)

  return expect_tests.Result(ret)


@expect_tests.test_generator
def GenTests():
  for test_name, test in gsubtreed_test_definitions.GSUBTREED_TESTS.iteritems():
    yield expect_tests.Test(
        __package__ + '.' + test_name,
        expect_tests.FuncCall(RunTest, test_name),
        expect_base=test_name, ext='yaml', break_funcs=[test],
        covers=(
            expect_tests.Test.covers_obj(RunTest) +
            expect_tests.Test.covers_obj(gsubtreed_test_definitions)
        ))
