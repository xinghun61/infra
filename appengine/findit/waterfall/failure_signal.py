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
    self.failed_targets = []  # A list of dict.
    self.failed_output_nodes = []  # A list of string.
    self.failed_edges = []  # A list of dict.

  def AddEdge(self, edge):
    if edge not in self.failed_edges:
      self.failed_edges.append(edge)

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
        self.files[file_path].extend(x for x in line_numbers
                                     if x not in self.files[file_path])
      else:
        self.files[file_path] = line_numbers[:]

    new_failed_targets = other_signal.get('failed_targets', [])
    for target in new_failed_targets:
      self.AddTarget(target)
    self.failed_output_nodes = list(
        set(self.failed_output_nodes + other_signal.get('failed_output_nodes',
                                                        [])))
    new_failed_edges = other_signal.get('failed_edges', [])
    for edge in new_failed_edges:
      self.AddEdge(edge)

  def ToDict(self):
    json_dict = {
        'files': self.files,
        'keywords': self.keywords,
    }
    if self.failed_targets:
      json_dict['failed_targets'] = self.failed_targets
    if self.failed_output_nodes:
      json_dict['failed_output_nodes'] = self.failed_output_nodes
    if self.failed_edges:
      json_dict['failed_edges'] = self.failed_edges
    return json_dict

  @staticmethod
  def FromDict(data):
    signal = FailureSignal()
    signal.files.update(copy.deepcopy(data.get('files', {})))
    signal.keywords.update(data.get('keywords', {}))
    signal.failed_targets = data.get('failed_targets', [])
    signal.failed_output_nodes = data.get('failed_output_nodes', [])
    signal.failed_edges = data.get('failed_edges', [])
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
    if self.failed_output_nodes:
      print '  Failed output nodes: %s' % ','.join(self.failed_output_nodes)
    if self.failed_edges:
      print ' Failed edges:'
      for edge in self.failed_edges:
        output_nodes = edge.get('output_nodes')
        rule = edge.get('rule')
        dependencies = edge.get('dependencies')
        if output_nodes:
          print '  Output nodes: %s' % output_nodes
        if rule:
          print '  Rule: %s' % rule
        if dependencies:
          print '  Dependencies: %s' % dependencies
