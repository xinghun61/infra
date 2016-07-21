# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Aggregator aggregates scorer results list passed in."""

class Aggregator(object):

  def Aggregate(self, data_list):
    raise NotImplementedError()

  def __call__(self, data_list):
    data_list = filter(lambda data: not data is None, data_list)
    if not data_list:
      return None

    return self.Aggregate(data_list)


# TODO(katesonia): Compare this mutiply aggregator with a vector of scores
# aggregator later.
class Multiplier(Aggregator):

  def Aggregate(self, data_list):
    result = 1.0
    for data in data_list:
      result *= data

    return result


class IdentityAggregator(Aggregator):

  def Aggregate(self, data_list):
    return data_list


class ChangedFilesAggregator(Aggregator):
  """Aggregates a list of changed files got from many scorers.

  Note: This Aggregator only aggregates the info part of each changed file.

  For example, the data_list is:
  [
      [
          {
              'file': 'f1',
              'blame_url': 'https://blame1',
              'info': 'f1 info scorer1'
          },
          {
              'file': 'f2',
              'blame_url': 'https://blame2',
              'info': 'f2 info scorer1'
          }
      ],
      [
          {
              'file': 'f1',
              'blame_url': 'https://blame1',
              'info': 'f1 info scorer2'
          },
          {
              'file': 'f2',
              'blame_url': 'https://blame2',
              'info': 'f2 info scorer2'
          }
      ]
  ]

  Aggregated result should be:
  [
      {
          'file': 'f1',
          'blame_url': 'https://blame1',
          'info': 'f1 info scorer1\nf1 info scorer2'
      },
      {
          'file': 'f2',
          'blame_url': 'https://blame2',
          'info': 'f2 info scorer1\nf2 info scorer2'
      }
  ]
  """

  def Aggregate(self, data_list):

    def AggregateFileInfos(file_info_list):
      """Aggregates file infos from different scorers for one file."""
      infos = []
      for file_info in file_info_list:
        if file_info['info']:
          infos.append(file_info['info'])

      return {
          'file': file_info_list[0]['file'],
          'blame_url': file_info_list[0]['blame_url'],
          'info': '\n'.join(infos)
      }

    aggregated_changed_files = []
    for data in zip(*data_list):
      aggregated_changed_files.append(AggregateFileInfos(data))

    return aggregated_changed_files
