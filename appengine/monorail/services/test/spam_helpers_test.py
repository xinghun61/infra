# coding=utf-8
from __future__ import division

import unittest

from services import spam_helpers


NUM_WORD_HASHES = 5


class SpamHelpersTest(unittest.TestCase):

  def testHashFeatures(self):
    hashes = spam_helpers._HashFeatures(tuple(), NUM_WORD_HASHES)
    self.assertEquals([0, 0, 0, 0, 0], hashes)

    hashes = spam_helpers._HashFeatures(('', ''), NUM_WORD_HASHES)
    self.assertEquals([1.0, 0, 0, 0, 0], hashes)

    hashes = spam_helpers._HashFeatures(('abc', 'abc def'), NUM_WORD_HASHES)
    self.assertEquals([0, 0, 2/3, 0, 1/3], hashes)

  def testGenerateFeaturesRaw(self):
    features = spam_helpers.GenerateFeaturesRaw(
      'abc', 'abc def http://www.google.com http://www.google.com',
      NUM_WORD_HASHES)
    self.assertEquals([1/2.75, 0.0, 1/5.5, 0.0, 1/2.2], features['word_hashes'])

    features = spam_helpers.GenerateFeaturesRaw('abc', 'abc def',
      NUM_WORD_HASHES)
    self.assertEquals([0.0, 0.0, 2/3, 0.0, 1/3], features['word_hashes'])

    # BMP Unicode
    features = spam_helpers.GenerateFeaturesRaw(
      u'abc’', u'abc ’ def', NUM_WORD_HASHES)
    self.assertEquals([0.0, 0.0, 0.25, 0.25, 0.5], features['word_hashes'])

    # Non-BMP Unicode
    features = spam_helpers.GenerateFeaturesRaw(u'abc國', u'abc 國 def',
      NUM_WORD_HASHES)
    self.assertEquals([0.0, 0.0, 0.25, 0.25, 0.5], features['word_hashes'])

    # A non-unicode bytestring containing unicode characters
    features = spam_helpers.GenerateFeaturesRaw('abc…', 'abc … def',
      NUM_WORD_HASHES)
    self.assertEquals([0.25, 0.0, 0.25, 0.25, 0.25], features['word_hashes'])

    # Empty input
    features = spam_helpers.GenerateFeaturesRaw('', '', NUM_WORD_HASHES)
    self.assertEquals([1.0, 0.0, 0.0, 0.0, 0.0], features['word_hashes'])
