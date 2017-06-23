# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class TestInfo(object):  # pragma: no cover.
  """Represents a test."""

  def __init__(self, master_name, builder_name, build_number, step_name,
               test_name):
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number
    self.step_name = step_name
    self.test_name = test_name

  def __repr__(self):
    return '%s/%s/%s/%s/%s' % (self.master_name, self.builder_name,
                               self.build_number, self.step_name,
                               self.test_name)

  def __eq__(self, other):
    return (isinstance(other, self.__class__) and
            self.master_name == other.master_name and
            self.builder_name == other.builder_name and
            self.build_number == other.build_number and
            self.step_name == other.step_name and
            self.test_name == other.test_name)
