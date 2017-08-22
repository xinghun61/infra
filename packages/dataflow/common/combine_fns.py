# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file

import apache_beam as beam


class ConvertToCSV(beam.CombineFn):
  """Convert elements to CSV format to be written out

  Transform for writing elements out in a CSV format. Can process elements
  of type dictonary or list. This transform only supports consistent elements,
  meaning dictionaries must all have the same keys and lists must have the
  same length and order. If provided a header, a list must already be in that
  order and a dictionary must have at least those fields.
  """
  def __init__(self, header=None):
    self.header = header

  def create_accumulator(self):
    return []

  def iterable(self, obj):
   """Returns an iterable for a dictionary or list

   Sorting dictionary keys assures that the CSV is in the same order
   for all dictionaries. If given a header, use the header fields as
   the iterable for the dictionary to preserve that order.
   """
   if isinstance(obj, dict):
     if self.header:
       return self.header
     keys = obj.keys()
     return sorted(keys)
   else:
     return range(len(obj))

  def add_input(self, accumulator, element):
    element_string = []
    for i in self.iterable(element):
      element_string.append(str(element[i]))
    accumulator.append(','.join(element_string) + '\n')
    return accumulator

  def merge_accumulators(self, accumulators):
    return sum(accumulators, [])

  def extract_output(self, accumulator):
    if self.header:
      accumulator.insert(0, ','.join(self.header) + '\n')
    return ''.join(accumulator)
