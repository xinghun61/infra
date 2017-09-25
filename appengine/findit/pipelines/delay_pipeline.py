# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import taskqueue

from gae_libs import pipelines


class DelayPipeline(pipelines.AsynchronousPipeline):
  """Delays pipeline execution by n seconds.

  Usage:
    delay = yield DelayPipeline(<n seconds>)
    with pipeline.After(delay):
      DoSomethingAfterDelay()
  """
  input_type = int
  output_type = int

  def RunImpl(self, seconds):
    task = self.get_callback_task(
        countdown=seconds, name='delay-' + self.pipeline_id)
    try:
      task.add(self.queue_name)
    except (taskqueue.TombstonedTaskError,
            taskqueue.TaskAlreadyExistsError):  # pragma: no cover
      pass
    return seconds

  def CallbackImpl(self, seconds, _):
    self.complete(seconds)