# coding=utf-8
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import StringIO
import unittest

from services import ml_helpers


NUM_WORD_HASHES = 5

TOP_WORDS = {'cat': 0, 'dog': 1, 'bunny': 2, 'chinchilla': 3, 'hamster': 4}
NUM_COMPONENT_FEATURES = len(TOP_WORDS)


class MLHelpersTest(unittest.TestCase):

  def testSpamHashFeatures(self):
    hashes = ml_helpers._SpamHashFeatures(tuple(), NUM_WORD_HASHES)
    self.assertEquals([0, 0, 0, 0, 0], hashes)

    hashes = ml_helpers._SpamHashFeatures(('', ''), NUM_WORD_HASHES)
    self.assertEquals([1.0, 0, 0, 0, 0], hashes)

    hashes = ml_helpers._SpamHashFeatures(('abc', 'abc def'), NUM_WORD_HASHES)
    self.assertEquals([0, 0, 2/3, 0, 1/3], hashes)

  def testComponentFeatures(self):

    features = ml_helpers._ComponentFeatures(['cat dog is not bunny'
                                              ' chinchilla hamster'],
                                             NUM_COMPONENT_FEATURES,
                                             TOP_WORDS)
    self.assertEquals([1, 1, 1, 1, 1], features)

    features = ml_helpers._ComponentFeatures(['none of these are features'],
                                             NUM_COMPONENT_FEATURES,
                                             TOP_WORDS)
    self.assertEquals([0, 0, 0, 0, 0], features)

    features = ml_helpers._ComponentFeatures(['do hamsters look like a'
                                             ' chinchilla'],
                                             NUM_COMPONENT_FEATURES,
                                             TOP_WORDS)
    self.assertEquals([0, 0, 0, 1, 0], features)

    features = ml_helpers._ComponentFeatures([''],
                                             NUM_COMPONENT_FEATURES,
                                             TOP_WORDS)
    self.assertEquals([0, 0, 0, 0, 0], features)

  def testGenerateFeaturesRaw(self):

    features = ml_helpers.GenerateFeaturesRaw(
        ['abc', 'abc def http://www.google.com http://www.google.com'],
      NUM_WORD_HASHES)
    self.assertEquals([1/2.75, 0.0, 1/5.5, 0.0, 1/2.2], features['word_hashes'])

    features = ml_helpers.GenerateFeaturesRaw(['abc', 'abc def'],
      NUM_WORD_HASHES)
    self.assertEquals([0.0, 0.0, 2/3, 0.0, 1/3], features['word_hashes'])

    features = ml_helpers.GenerateFeaturesRaw(['do hamsters look like a'
                                               ' chinchilla'],
                                              NUM_COMPONENT_FEATURES,
                                              TOP_WORDS)
    self.assertEquals([0, 0, 0, 1, 0], features['word_features'])

    # BMP Unicode
    features = ml_helpers.GenerateFeaturesRaw(
        [u'abc’', u'abc ’ def'], NUM_WORD_HASHES)
    self.assertEquals([0.0, 0.0, 0.25, 0.25, 0.5], features['word_hashes'])

    # Non-BMP Unicode
    features = ml_helpers.GenerateFeaturesRaw([u'abc國', u'abc 國 def'],
      NUM_WORD_HASHES)
    self.assertEquals([0.0, 0.0, 0.25, 0.25, 0.5], features['word_hashes'])

    # A non-unicode bytestring containing unicode characters
    features = ml_helpers.GenerateFeaturesRaw(['abc…', 'abc … def'],
      NUM_WORD_HASHES)
    self.assertEquals([0.25, 0.0, 0.25, 0.25, 0.25], features['word_hashes'])

    # Empty input
    features = ml_helpers.GenerateFeaturesRaw(['', ''], NUM_WORD_HASHES)
    self.assertEquals([1.0, 0.0, 0.0, 0.0, 0.0], features['word_hashes'])

  def test_from_file(self):
    csv_file = StringIO.StringIO('''
      "spam","the subject 1","the contents 1","spammer@gmail.com"
      "ham","the subject 2"
      "spam","the subject 3","the contents 2","spammer2@gmail.com"
    '''.strip())
    samples, skipped = ml_helpers.spam_from_file(csv_file)
    self.assertEquals(len(samples), 2)
    self.assertEquals(skipped, 1)
    self.assertEquals(len(samples[1]), 3, 'Strips email')
    self.assertEquals(samples[1][2], 'the contents 2')

  def test_transform_csv_to_features(self):
    training_data = [
      ['spam', 'subject 1', 'contents 1'],
      ['ham', 'subject 2', 'contents 2'],
      ['spam', 'subject 3', 'contents 3'],
    ]
    X, y = ml_helpers.transform_spam_csv_to_features(training_data)

    self.assertIsInstance(X, list)
    self.assertIsInstance(X[0], dict)
    self.assertIsInstance(y, list)

    self.assertEquals(len(X), 3)
    self.assertEquals(len(y), 3)

    self.assertEquals(len(X[0]['word_hashes']), 500)
    self.assertEquals(y, [1, 0, 1])
