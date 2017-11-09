# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A simple profiler object to track how time is spent on a request.

The profiler is called from application code at the begining and
end of each major phase and subphase of processing.  The profiler
object keeps track of how much time was spent on each phase or subphase.

This class is useful when developers need to understand where
server-side time is being spent.  It includes durations in
milliseconds, and a simple bar chart on the HTML page.

On-page debugging and performance info is useful because it makes it easier
to explore performance interactively.
"""

import logging
import threading
import time

from contextlib import contextmanager


class Profiler(object):
  """Object to record and help display request processing profiling info.

  The Profiler class holds a list of phase objects, which can hold additional
  phase objects (which are subphases).  Each phase or subphase represents some
  meaningful part of this application's HTTP request processing.
  """

  _COLORS = ['900', '090', '009', '360', '306', '036',
             '630', '630', '063', '333']

  def __init__(self):
    """Each request processing profile begins with an empty list of phases."""
    self.top_phase = _Phase('overall profile', -1, None)
    self.current_phase = self.top_phase
    self.next_color = 0
    self.original_thread_id = threading.current_thread().ident

  def StartPhase(self, name='unspecified phase'):
    """Begin a (sub)phase by pushing a new phase onto a stack."""
    if self.original_thread_id != threading.current_thread().ident:
      return  # We only profile the main thread.
    color = self._COLORS[self.next_color % len(self._COLORS)]
    self.next_color += 1
    self.current_phase = _Phase(name, color, self.current_phase)

  def EndPhase(self):
    """End a (sub)phase by poping the phase stack."""
    if self.original_thread_id != threading.current_thread().ident:
      return  # We only profile the main thread.
    self.current_phase = self.current_phase.End()

  @contextmanager
  def Phase(self, name='unspecified phase'):
    """Context manager to automatically begin and end (sub)phases."""
    self.StartPhase(name)
    try:
      yield
    finally:
      self.EndPhase()

  def LogStats(self):
    """Log sufficiently-long phases and subphases, for debugging purposes."""
    self.top_phase.LogStats()


class _Phase(object):
  """A _Phase instance represents a period of time during request processing."""

  def __init__(self, name, color, parent):
    """Initialize a (sub)phase with the given name and current system clock."""
    self.start = time.time()
    self.name = name
    self.color = color
    self.subphases = []
    self.elapsed_seconds = None
    self.ms = 'in_progress'  # shown if the phase never records a finish.
    self.uncategorized_ms = None
    self.parent = parent
    if self.parent is not None:
      self.parent._RegisterSubphase(self)

  def _RegisterSubphase(self, subphase):
    """Add a subphase to this phase."""
    self.subphases.append(subphase)

  def End(self):
    """Record the time between the start and end of this (sub)phase."""
    self.elapsed_seconds = time.time() - self.start
    self.ms = str(int(self.elapsed_seconds * 1000))
    for sub in self.subphases:
      if sub.elapsed_seconds is None:
        logging.warn('issue3182: subphase is %r', sub and sub.name)
    categorized = sum(sub.elapsed_seconds or 0.0 for sub in self.subphases)
    self.uncategorized_ms = int((self.elapsed_seconds - categorized) * 1000)
    return self.parent

  def LogStats(self):
    # Phases that took longer than 30ms are interesting.
    if self.elapsed_seconds > 0.03:
      logging.info('%5s: %s', self.ms, self.name)
      for subphase in self.subphases:
        subphase.LogStats()
