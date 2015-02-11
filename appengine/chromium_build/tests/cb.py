#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import inspect
import os
import re

import app
import handler

from tests.testing_utils import testing


class CbTestCase(testing.AppengineTestCase):
  TEST_DIR = os.path.dirname(__file__)

  app_module = handler.application

  def _expect_dir(self):
    """Locate the directory containing this test's expectations.

    First we look for whether this was called via a test_*() method.  If
    we find such a method in the stack, we set the expectations directory
    to be based on that location.

    If we can't find a test_*() method on the stack, then we set the
    expectations directory to just be similar to the test filename.
    """
    # Search for a *_test.py filename on the stack.  We should find this, so
    # we raise an Exception if we can't find it.
    test_filename = None
    for stack in inspect.stack():
      if stack[1].endswith('_test.py'):
        md = re.match(r'.*/([^/]*_test).py$', stack[1])
        if md and md.group(1):
          test_filename = md.group(1)
          break
    if test_filename is None:
      raise Exception('can not determine test_filename')

    # Search for a test_* method on the stack.  If we find it, we'll include
    # it in the pathname to the expectations directory.
    test_method = None
    for stack in inspect.stack():
      if stack[3].startswith('test_'):
        test_method = stack[3]
        break
    expect_dir = os.path.join(self.TEST_DIR, test_filename + '.files')
    if test_method is not None:
        expect_dir = os.path.join(expect_dir, test_method)
    return expect_dir

  def _get_path(self, filename):
    return os.path.join(self._expect_dir(), filename)

  def read_file(self, filename):
    with open(self._get_path(filename)) as fh:
      return fh.read()
    return None

  def write_file(self, filename, content):
    with open(self._get_path(filename), 'w') as fh:
      fh.write(content)
  
  @staticmethod
  def save_page(localpath, content):
    page_data = {}
    page_data['content'] = content
    fetch_timestamp = datetime.datetime.now()
    model = app.Page(localpath=localpath, content=None,
                     fetch_timestamp=fetch_timestamp)
    model.put()
    app.save_page(model, localpath=localpath, fetch_timestamp=fetch_timestamp,
                  page_data=page_data)
    return model
