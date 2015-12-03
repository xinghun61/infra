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
    self.failed_targets = []

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

  def AddTarget(self, failed_target):
    if failed_target not in self.failed_targets:
      self.failed_targets.append(failed_target)

  def MergeFrom(self, other_signal):
    """Adds files in signal to self, adds line number if file exists."""
    # TODO: Merge keywords later after we add support for keywords.
    for file_path, line_numbers in other_signal['files'].iteritems():
      if file_path in self.files:
        self.files[file_path].extend(
            x for x in line_numbers if x not in self.files[file_path])
      else:
        self.files[file_path] = line_numbers[:]

    new_failed_targets = other_signal.get('failed_targets', [])
    for target in new_failed_targets:
      self.AddTarget(target)

  def ToDict(self):
    if self.failed_targets:
      return {
          'files': self.files,
          'keywords': self.keywords,
          'failed_targets': self.failed_targets
      }

    return {
        'files': self.files,
        'keywords': self.keywords,
    }

  @staticmethod
  def FromDict(data):
    signal = FailureSignal()
    signal.files.update(copy.deepcopy(data.get('files', {})))
    signal.keywords.update(data.get('keywords', {}))
    signal.failed_targets = data.get('failed_targets', [])
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
    if self.failed_targets:
      print 'Failed Targets:'
      for source_target in self.failed_targets:
        target = source_target.get('target')
        source = source_target.get('source')
        if target:
          print '  Target: %s' % target
        if source:
          print '  Source: %s' % source
