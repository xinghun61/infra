# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import os
import shutil
import sys
import tempfile

import infra
from infra.services import gnumbd

GNUMBD_PATH = os.path.abspath(os.path.dirname(gnumbd.__file__))

ROOT_PATH = os.path.abspath(os.path.dirname(os.path.dirname(infra.__file__)))
EXPECT_PATH = os.path.join(
    ROOT_PATH, '..', 'build', 'scripts', 'slave', 'unittests')
DEPOT_TOOLS_PATH = os.path.join(ROOT_PATH, 'depot_tools')
sys.path.insert(0, EXPECT_PATH)
sys.path.insert(0, DEPOT_TOOLS_PATH)

import expect_tests  # pylint: disable=F0401

def GenTests(tmpdir):
  from infra.services.gnumbd.test import (
      gnumbd_smoketests_main, util_test, data_test, git_test, config_test)

  for test in gnumbd_smoketests_main.GenTests(tmpdir):
    yield test

  for test_mod in (util_test, data_test, git_test, config_test):
    for test in expect_tests.UnitTestModule(test_mod):
      yield test


#### Actual tests
def main():
  suffix = '.gnumbd_smoketests'
  tmpdir = tempfile.mkdtemp(suffix)
  for p in glob.glob(os.path.join(os.path.dirname(tmpdir), '*'+suffix)):
    if p != tmpdir:
      shutil.rmtree(p)

  try:
    expect_tests.main(
        'gnumbd_tests',
        lambda: GenTests(tmpdir),
        [
            os.path.join(GNUMBD_PATH, '*.py'),
            os.path.join(GNUMBD_PATH, 'test', '*_test.py'),
        ], [
            os.path.join(GNUMBD_PATH, 'test', '__main__.py')
        ],
        cover_branches=True,
    )
  finally:
    try:
      shutil.rmtree(tmpdir)
    except Exception:
      pass

if __name__ == '__main__':
  main()
