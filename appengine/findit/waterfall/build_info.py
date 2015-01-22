# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class BuildInfo(object):  # pragma: no cover
  """Represents a build cycle of a build bot."""

  def __init__(self, master_name, builder_name, build_number):
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number
    self.build_start_time = None
    self.chromium_revision = None
    self.completed = False
    self.result = None
    self.blame_list = []
    self.failed_steps = []
    self.passed_steps = []

  def PrettyPrint(self):
    print 'master: %s' % self.master_name
    print 'builder: %s' % self.builder_name
    print 'build: %s' % self.build_number
    print 'start time: %s' % self.build_start_time
    print 'chromium revision: %s' % self.chromium_revision
    print 'completed: %s' % self.completed
    print 'result: %s' % self.result
    print 'CLs: %s' % ', '.join(self.blame_list)
    print 'Failed steps: %s' % ', '.join(self.failed_steps)
    print 'Passed steps: %s' % ', '.join(self.passed_steps)
