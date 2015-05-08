# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Convenience functions for code calling the multiprocessing module."""

import contextlib
import multiprocessing


@contextlib.contextmanager
def MultiPool(processes):
  """Manages a multiprocessing.Pool making sure to close the pool when done.

  This will also call pool.terminate() when an exception is raised (and
  re-raised the exception to the calling procedure can handle it).

  If you plan on using a multiprocess pool, take a look at
  http://bugs.python.org/issue12157 and
  http://stackoverflow.com/a/1408476/3984761.
  """
  try:
    pool = multiprocessing.Pool(processes=processes)
    yield pool
    pool.close()
  except:
    pool.terminate()
    raise
  finally:
    pool.join()


def safe_map(func, args, processes):  # pragma: no cover
  """Executes a function over multiple sets of arguments in parallel.

  This works around two gotchas easily encountered when using
  multiprocessing.Pool.map_async(). Specifically, that map_async() can hang if
  the arguent count is an empty list, and that KeyboardInterrupts are not
  handled properly.

  func must be a real, top-level function (cannot be a nested function or
       lambda, see http://stackoverflow.com/q/8804830/3984761). It should take
       a single argument.

  args is an iterable of arguments over which repeated func calls are made.

  processes is the number of processes to use for execution.
  """

  # Prevent map from hanging, see http://bugs.python.org/issue12157.
  if not args:
    return []

  with MultiPool(processes) as pool:
    # This strange invocation is so ctrl-c can interrupt the map_async. See
    # http://stackoverflow.com/a/1408476/3984761 for details.
    return pool.map_async(func, args).get(9999999)
