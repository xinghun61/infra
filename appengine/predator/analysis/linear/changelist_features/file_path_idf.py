# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math
import os

from analysis.linear.feature import Feature
from analysis.linear.feature import FeatureValue
from analysis.linear.feature import LinearlyScaled


def LogRegressNomalize(value):
  """Uses log regress to normalize (-inf, inf) to [0, 1]."""
  value_exp = math.exp(value)
  return value_exp / (value_exp + 1)


def GetDocumentNumberForKeyword(keyword, inverted_index_table):
  """Gets the number of documents which contains the keyword."""
  inverted_index = inverted_index_table.Get(keyword)
  if not inverted_index:
    return 0

  return inverted_index.n_of_doc


def GetTotalDocumentNumber(inverted_index_table):
  """Gets the total number of documents in a document collection."""
  return inverted_index_table.GetRoot().n_of_doc


def ComputeIdf(keyword, inverted_index_table):
  """Computes Idf(Inverse document frequency) of a keyword in a collection."""
  document_num = GetDocumentNumberForKeyword(keyword, inverted_index_table)
  total_document_num = GetTotalDocumentNumber(inverted_index_table)

  return math.log(total_document_num / float(1 + document_num))


class FilePathIdfFeature(Feature):
  """Returns the maximum idf value in (0, 1) of all crashed files paths.

  Because some term like 'the' is so common, term frequency will tend to
  incorrectly emphasize documents which happen to use the word 'the' more
  frequently, without giving enough weight to the more meaningful terms 'brown'
  and 'cow'. The term 'the' is not a good keyword to distinguish relevant and
  non-relevant documents and terms, unlike the less common words 'brown' and
  'cow'. Hence an inverse document frequency factor is incorporated which
  diminishes the weight of terms that occur very frequently in the document set
  and increases the weight of terms that occur rarely.

  In a crash, we can often see some files like base/callback.h, base/..., those
  file are so common in stacktrace that they are less likely to be blamed as
  culprit. In this case, we can use idf to reduce the importance of those files.

  This value of this feature returns most important file that a suspect touched.
  The higher the value the more important the file that suspect touched.
  """
  def __init__(self, inverted_index_table):
    """
    Args:
      inverted_index_table (InvertedIndex): An (subclass of) InvertedIndex,
      which is a table mapping a keyword to the number of documents that
      contains this keyword, by using:
        number_of_documents = inverted_index_table.Get(keyword)
    """
    self._inverted_index_table = inverted_index_table

  @property
  def name(self):
    return 'FilePathIdf'

  def __call__(self, report):
    """The maximum idf(inverse document frequecy) across all files and stacks.

    Args:
      report (CrashReport): the crash report being analyzed.

    Returns:
      A function from ``Suspect`` to the idf of a crash.
    """
    def FeatureValueGivenReport(suspect, matches):  # pylint: disable=W0613
      """Computes ``FeatureValue`` for a suspect.

      Args:
        suspect (Suspect): The suspected changelog and some meta information
          about it.
        matches(dict): Dict mapping crashed group(CrashedFile, CrashedDirectory)
          to a list of ``CrashMatch``s representing all frames and all touched
          files matched in the same crashed group(same crashed file or crashed
          directory).

      Returns:
        The ``FeatureValue`` of this feature.
      """
      if not matches:
        return FeatureValue(name=self.name,
                            value=0,
                            reason=None,
                            changed_files=None)

      def GetMaxIdfInMatches(matches):
        """Gets the maximum idf and the file path with the maximum idf."""
        file_paths = [
            os.path.join(frame_info.frame.dep_path, frame_info.frame.file_path)
            for match in matches.itervalues()
            for frame_info in match.frame_infos
        ]
        max_idf, max_idf_file_path = max(
            [(ComputeIdf(file_path, self._inverted_index_table), file_path)
              for file_path in file_paths],
            key=lambda item: item[0])

        return max_idf, max_idf_file_path

      logging.info('Computing crash idf feature')
      max_idf, max_idf_file_path = GetMaxIdfInMatches(matches)
      value = LogRegressNomalize(max_idf)
      reason = ['Suspected changelist modified the file %s, which is not '
                'commonly changed.' % os.path.basename(max_idf_file_path)]

      return FeatureValue(self.name, value, reason, None)

    return FeatureValueGivenReport
