# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(pgervais): this file has no tests

from contextlib import contextmanager
import base64
import pickle
import traceback

from google.appengine.ext import testbed
from google.appengine.api import urlfetch

from mock import Mock
from test.testing_utils import testing
import main


def fake_urlfetch_fetch():  # pragma: no cover
  fetch = Mock()
  fetch.return_value.status_code = 404
  fetch.return_value.headers = {}
  fetch.return_value.content = ''
  return fetch


class CrBuildTestCase(testing.AppengineTestCase):  # pragma: no cover
  app_module = main.app

  def __init__(self, *args, **kwargs):
    super(CrBuildTestCase, self).__init__(*args, **kwargs)
    self.urlfetch_fetch = None

  def setUp(self):
    super(CrBuildTestCase, self).setUp()
    self.tear_downs = []
    self.mock_current_user(user_id='johndoe', user_email='johndoe@chromium.org')
    self.urlfetch_fetch = fake_urlfetch_fetch()
    self.mock(urlfetch, 'fetch', self.urlfetch_fetch)

  def _run_tear_downs(self):
    some_failed = False
    for td in self.tear_downs:
      try:
        td()
      except Exception:
        traceback.print_exc()
        some_failed = True
    self.tear_downs = []
    if some_failed:
      self.fail("Tear down failed")

  def tearDown(self):
    try:
      self._run_tear_downs()
    finally:
      super(CrBuildTestCase, self).tearDown()

  def execute_deferred(self, queue_name='default'):
    """Executes deferred push tasks.

    Executes existing tasks and those generated during execution until there are
    no tasks left.

    Caution: assumes that all tasks in |queue_name| queue are deferred.
    """
    taskq = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)

    while True:
      tasks = taskq.GetTasks(queue_name)
      taskq.FlushQueue(queue_name)
      if not tasks:
        break
      for task in tasks:
        # TODO(nodir): check that task is actually a deferred task.
        (func, args, _) = pickle.loads(base64.b64decode(task['body']))
        func(*args)
