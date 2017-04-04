# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains util functions that local scripts can use."""

import atexit
from datetime import datetime
import functools
import logging
import os
import pickle
import Queue
import re
import subprocess
import sys
import threading
import time
import traceback

MAX_THREAD_NUMBER = 30
TASK_QUEUE = None
GIT_HASH_PATTERN = re.compile(r'^[0-9a-fA-F]{40}$')


def SetUpSystemPaths():  # pragma: no cover
  """Sets system paths so as to import modules in findit, third_party and
  appengine."""
  findit_root_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                 os.path.pardir)
  first_party_dir = os.path.join(findit_root_dir, 'first_party')
  third_party_dir = os.path.join(findit_root_dir, 'third_party')
  appengine_sdk_dir = os.path.join(findit_root_dir, os.path.pardir,
                                   os.path.pardir, os.path.pardir,
                                   'google_appengine')

  sys.path.insert(1, appengine_sdk_dir)

  import dev_appserver
  dev_appserver.fix_sys_path()

  # Add Findit root dir to sys.path so that modules in Findit is available.
  sys.path.insert(1, findit_root_dir)
  # Add App Engine SDK dir to sys.path.
  sys.path.insert(1, third_party_dir)
  sys.path.insert(1, first_party_dir)

  import google
  # protobuf and GAE have package name conflict on 'google'.
  # Add this to solve the conflict.
  google.__path__.insert(0, os.path.join(third_party_dir, 'google'))


def SignalWorkerThreads():  # pragma: no cover
  """Puts signal worker threads into task queue."""
  global TASK_QUEUE  # pylint: disable=W0602
  if not TASK_QUEUE:
    return

  for _ in range(MAX_THREAD_NUMBER):
    TASK_QUEUE.put(None)

  # Give worker threads a chance to exit.
  # Workaround the harmless bug in python 2.7 below.
  time.sleep(1)


atexit.register(SignalWorkerThreads)


def Worker():  # pragma: no cover
  global TASK_QUEUE  # pylint: disable=W0602
  while True:
    try:
      task = TASK_QUEUE.get()
      if not task:
        return
    except TypeError:
      # According to http://bugs.python.org/issue14623, this is a harmless bug
      # in python 2.7 which won't be fixed.
      # The exception is raised on daemon threads when python interpreter is
      # shutting down.
      return

    function, args, kwargs, result_semaphore = task
    try:
      function(*args, **kwargs)
    except Exception:
      print 'Caught exception in thread.'
      print traceback.format_exc()
      # Continue to process tasks in queue, in case every thread fails, the
      # main thread will be waiting forever.
      continue
    finally:
      # Signal one task is done in case of exception.
      result_semaphore.release()


def RunTasks(tasks):  # pragma: no cover
  """Run given tasks. Not thread-safe: no concurrent calls of this function.

  Return after all tasks were completed. A task is a dict as below:
    {
      'function': the function to call,
      'args': the positional argument to pass to the function,
      'kwargs': the key-value arguments to pass to the function,
    }
  """
  if not tasks:
    return

  global TASK_QUEUE
  if not TASK_QUEUE:
    TASK_QUEUE = Queue.Queue()
    for index in range(MAX_THREAD_NUMBER):
      thread = threading.Thread(target=Worker, name='worker_%s' % index)
      # Set as daemon, so no join is needed.
      thread.daemon = True
      thread.start()

  result_semaphore = threading.Semaphore(0)
  # Push task to task queue for execution.
  for task in tasks:
    TASK_QUEUE.put((task['function'], task.get('args', []),
                    task.get('kwargs', {}), result_semaphore))

  # Wait until all tasks to be executed.
  for _ in tasks:
    result_semaphore.acquire()


def GetCommandOutput(command):
  SetUpSystemPaths()

  # The lib is in predator/ root dir, and can be imported only when sys.path
  # gets set up.
  from libs.cache_decorator import Cached
  from local_cache import LocalCache  # pylint: disable=W

  @Cached(LocalCache(), namespace='Command-output')
  def CachedGetCommandOutput(command):
    p = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdoutdata, stderrdata = p.communicate()

    if p.returncode != 0:
      raise Exception('Error running command %s: %s' % (command, stderrdata))

    return stdoutdata

  return CachedGetCommandOutput(command)


def GetLockedMethod(cls, method_name, lock):  # pragma: no cover
  """Returns a class/object method serialized with lock."""
  method = getattr(cls, method_name)

  def LockedMethod(cls, *args, **kwargs):  # pylint: disable=W
    with lock:
      return method(*args, **kwargs)

  return functools.partial(LockedMethod, cls)


# TODO(katesonia): Move this to gae_libs.
# TODO(crbug.com/662540): Add unittests.
def GetFilterQuery(query, time_property, start_date, end_date,
                   property_values=None,
                   datetime_pattern='%Y-%m-%d'):  # pragma: no cover.
  """Gets query with filters.

  There are 2 kinds for filters:
    (1) The time range filter defined by ``time_property``, ``start_date`` and
    ``end_date``. Note, the format of ``start_date`` and ``end_date`` should be
    consistent with ``datetime_pattern``.
    (2) The values of properties set by ``property_values``.
  """
  start_date = datetime.strptime(start_date, datetime_pattern)
  end_date = datetime.strptime(end_date, datetime_pattern)

  if property_values:
    for cls_property, value in property_values.iteritems():
      if isinstance(value, list):
        query = query.filter(cls_property.IN(value))
      else:
        query = query.filter(cls_property == value)

  return query.filter(time_property >= start_date).filter(
      time_property < end_date)


# TODO(crbug.com/662540): Add unittests.
def EnsureDirExists(path):  # pragma: no cover
  directory = os.path.dirname(path)
  # TODO: this has a race condition. Should ``try: os.makedirs`` instead,
  # discarding the error and returning if the directory already exists.
  if os.path.exists(directory):
    return

  os.makedirs(directory)


# TODO(crbug.com/662540): Add unittests.
def FlushResult(result, result_path, serializer=pickle,
                print_path=False):  # pragma: no cover
  if print_path:
    print '\nFlushing results to', result_path

  EnsureDirExists(result_path)
  with open(result_path, 'wb') as f:
    serializer.dump(result, f)


# TODO(crbug.com/662540): Add unittests.
def IsGitHash(revision):  # pragma: no cover
  return GIT_HASH_PATTERN.match(str(revision)) or revision.lower() == 'master'


# TODO(crbug.com/662540): Add unittests.
def ParseGitHash(revision, repo_path='.'):  # pragma: no cover
  """Gets git hash of a revision."""
  if IsGitHash(revision):
    return revision

  try:
    # Can parse revision like 'HEAD', 'HEAD~3'.
    return subprocess.check_output(
        'cd %s; git rev-parse %s' % (
            repo_path, revision), shell=True).replace('\n', '')
  except: # pylint: disable=W
    logging.error('Failed to parse git hash for %s\nStacktrace:\n%s',
                  revision, traceback.format_exc())
    return None
