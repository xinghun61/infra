# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import taskqueue
from google.appengine.ext import ndb


@ndb.tasklet
def enqueue_async(
    queue_name, task_kwargs, transactional=True
):  # pragma: no cover
  """Enqueues tasks. Mocked in tests.

  kwargs['payload'] and kwargs['retry_options'] may be dicts.
  Payload would be serialized to JSON.
  """
  tasks = []
  for kwargs in task_kwargs:
    kwargs = kwargs.copy()
    if isinstance(kwargs.get('payload'), dict):
      kwargs['payload'] = json.dumps(kwargs.get('payload'), sort_keys=True)

    if isinstance(kwargs.get('retry_options'), dict):
      kwargs['retry_options'] = taskqueue.TaskRetryOptions(
          **kwargs['retry_options']
      )
    tasks.append(taskqueue.Task(**kwargs))

  q = taskqueue.Queue(queue_name)
  # Cannot just return add_async's return value because it is
  # a non-Future object and does not play nice with `yield fut1, fut2` construct
  yield q.add_async(tasks, transactional=transactional)
