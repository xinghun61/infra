# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Test for monorail.framework.profiler."""

import unittest

from framework import profiler


class ProfilerTest(unittest.TestCase):

  def testTopLevelPhase(self):
    prof = profiler.Profiler()
    self.assertEquals(prof.current_phase.name, 'overall profile')
    self.assertEquals(prof.current_phase.parent, None)
    self.assertEquals(prof.current_phase, prof.top_phase)
    self.assertEquals(prof.next_color, 0)

  def testSinglePhase(self):
    prof = profiler.Profiler()
    self.assertEquals(prof.current_phase.name, 'overall profile')
    with prof.Phase('test'):
      self.assertEquals(prof.current_phase.name, 'test')
      self.assertEquals(prof.current_phase.parent.name, 'overall profile')
    self.assertEquals(prof.current_phase.name, 'overall profile')
    self.assertEquals(prof.next_color, 1)

  def testSubphaseExecption(self):
    prof = profiler.Profiler()
    try:
      with prof.Phase('foo'):
        with prof.Phase('bar'):
          pass
        with prof.Phase('baz'):
          raise Exception('whoops')
    except Exception as e:
      self.assertEquals(e.message, 'whoops')
    finally:
      self.assertEquals(prof.current_phase.name, 'overall profile')
      self.assertEquals(
          prof.top_phase.subphases[0].subphases[1].name, 'baz')


if __name__ == '__main__':
  unittest.main()
