# coding=utf-8

import unittest

from services import spam_helpers

class SpamHelpersTest(unittest.TestCase):

  def testExtractUrls(self):
    urls = spam_helpers._ExtractUrls('')
    self.assertEquals(0, len(urls))
    urls = spam_helpers._ExtractUrls('check this out: http://google.com')
    self.assertEquals(1, len(urls))
    self.assertEquals(['http://google.com'], urls)

  def testHashFeatures(self):
    hashes = spam_helpers._HashFeatures(tuple(), 5)
    self.assertEqual(5, len(hashes))
    self.assertEquals([0, 0, 0, 0, 0], hashes)

    hashes = spam_helpers._HashFeatures(('', ''), 5)
    self.assertEqual(5, len(hashes))
    self.assertEquals([1.0, 0, 0, 0, 0], hashes)

    hashes = spam_helpers._HashFeatures(('abc', 'abc def'), 5)
    self.assertEqual(5, len(hashes))
    self.assertEquals([0, 0, 0.6666666666666666, 0, 0.3333333333333333],
        hashes)

  def testGenerateFeatures(self):
    features = spam_helpers.GenerateFeatures(
        'abc', 'abc def http://www.google.com http://www.google.com',
        5)
    self.assertEquals(11, len(features))
    self.assertEquals(['2', '1', '3', '11', '51', '39',
        '0.363636', '0.000000', '0.181818', '0.000000', '0.454545'], features)

    features = spam_helpers.GenerateFeatures(
        'abc', 'abc def', 5)
    self.assertEquals(11, len(features))
    self.assertEquals(['0', '0', '3', '11', '7', '15',
        '0.000000', '0.000000', '0.666667', '0.000000', '0.333333'], features)

    # BMP Unicode
    features = spam_helpers.GenerateFeatures(
        u'abc’', u'abc ’ def', 5)
    self.assertEquals(11, len(features))
    self.assertEquals(['0', '0', '6', '14', '11', '19',
        '0.000000', '0.000000', '0.250000', '0.250000', '0.500000'], features)

    # Non-BMP Unicode
    features = spam_helpers.GenerateFeatures(
        u'abc國', u'abc 國 def', 5)
    self.assertEquals(11, len(features))
    self.assertEquals(['0', '0', '6', '14', '11', '19',
        '0.000000', '0.000000', '0.250000', '0.250000', '0.500000'], features)

    # A non-unicode bytestring containing unicode characters
    features = spam_helpers.GenerateFeatures(
        'abc…', 'abc … def', 5)
    self.assertEquals(11, len(features))
    self.assertEquals(['0', '0', '6', '14', '11', '19',
        '0.250000', '0.000000', '0.250000', '0.250000', '0.250000'], features)

    # Empty input
    features = spam_helpers.GenerateFeatures(
        '', '', 5)
    self.assertEquals(11, len(features))
    self.assertEquals(['0', '0', '0', '8', '0', '8',
        '1.000000', '0.000000', '0.000000', '0.000000', '0.000000'], features)

  def testGenerateFeaturesRaw(self):
    num_word_hashes = 5
    features = spam_helpers.GenerateFeaturesRaw(
        'abc', 'abc def http://www.google.com http://www.google.com',
        num_word_hashes)
    self.assertEquals({
      'num_urls': 2,
      'num_duplicate_urls': 1,
      'uncompressed_summary_len': 3,
      'compressed_summary_len': 11,
      'uncompressed_description_len': 51,
      'compressed_description_len': 39,
      'word_hashes': [
        0.36363636363636365,
        0.0,
        0.18181818181818182,
        0.0,
        0.45454545454545453
      ],
    }, features)

    self.assertEquals(num_word_hashes, len(features['word_hashes']))

