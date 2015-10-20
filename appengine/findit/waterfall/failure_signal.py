# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy


class FailureSignal(object):
  """Represents the signals extracted from a failed step or test."""

  def __init__(self):
    self.files = collections.defaultdict(list)
    self.keywords = collections.defaultdict(int)

  def AddFile(self, file_path, line_number=None):
    line_numbers = self.files[file_path]
    if line_number:
      line_number = int(line_number)
      if line_number not in line_numbers:
        line_numbers.append(line_number)

  def AddKeyword(self, keyword):
    keyword = keyword.strip()
    if keyword:
      self.keywords[keyword] += 1

  def ToDict(self):
    return {
      'files': self.files,
      'keywords': self.keywords,
    }

  @staticmethod
  def FromDict(data):
    signal = FailureSignal()
    signal.files.update(copy.deepcopy(data.get('files', {})))
    signal.keywords.update(data.get('keywords', {}))
    return signal

  def PrettyPrint(self):  # pragma: no cover
    if self.files:
      print 'Files:'
      for file_path, line_numbers in self.files.iteritems():
        print '  %s : %s' % (file_path, ','.join(map(str, line_numbers)))
    if self.keywords:
      print 'Keywords:'
      for keyword, count in self.keywords.iteritems():
        print '  %s (%d)' % (keyword, count)
