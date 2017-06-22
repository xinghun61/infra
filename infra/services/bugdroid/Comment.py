# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re


class Comment(object):

  def __init__(self):
    '''
    Constructor
    '''
    self.author = None
    self.blocked_on = []
    self.cc = None
    self.comment = None
    self.created = None
    self.labels = []
    self.merged_into = []
    self.summary = None
    self.status = None
    self.id = 0
      
  def hasLabelContaining(self, regex):
    for label in self.labels:
      if re.search(regex, label, re.DOTALL | re.IGNORECASE):
        return True
    return False

  def getLabelsContaining(self, regex):
    rtn = []
    for label in self.labels:
      if re.search(regex, label, re.DOTALL | re.IGNORECASE):
        rtn.append(label)
    return rtn

  def hasLabelMatching(self, regex):
    for label in self.labels:
      if re.match(regex + '\Z', label, re.DOTALL | re.IGNORECASE):
        return True
    return False

  def hasLabel(self, value):
    for label in self.labels:
      if label.lower() == value.lower():
        return True
    return False        