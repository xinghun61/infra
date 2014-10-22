# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import logging
import struct

from datetime import datetime

from google.appengine.ext import ndb

from .testname import TestName
from .jsonresults import JsonResults

class StepResult(ndb.Model):
  """Stores results for a single buildbot step (e.g, browser_tests).

  The results for all test cases included in the step are stored in a
  bit-packed blob, for compactness.  The TestName class maintains a
  global dict of all known test names, mapped to integer keys; this
  class stores the integer keys rather than test name strings.  The layout
  of a test result entry in the packed struct is:

  test name key: unsigned integer, 4 bytes
  test run time: float, 4 bytes
  expected result: unsigned integer, 1 byte
  number of actual results: unsigned integer, 1 byte
  actual results: array of 1-byte unsigned integers
  """

  # Test status constants
  (PASS,
   FAIL,
   SKIP,
   NOTRUN,
   CRASH,
   TIMEOUT,
   MISSING,
   LEAK,
   SLOW,
   TEXT,
   AUDIO,
   IMAGE,
   IMAGETEXT,
   REBASELINE,
   NEEDSREBASELINE,
   NEEDSMANUALREBASELINE) = range(16)

  STR2RESULT = {
      'PASS': PASS,
      'FAIL': FAIL,
      'SKIP': SKIP,
      'NOTRUN': NOTRUN,
      'CRASH': CRASH,
      'TIMEOUT': TIMEOUT,
      'MISSING': MISSING,
      'LEAK': LEAK,
      'SLOW': SLOW,
      'TEXT': TEXT,
      'AUDIO': AUDIO,
      'IMAGE': IMAGE,
      'IMAGETEXT': IMAGETEXT,
      'REBASELINE': REBASELINE,
      'NEEDSREBASELINE': NEEDSREBASELINE,
      'NEEDSMANUALREBASELINE': NEEDSMANUALREBASELINE,
  }

  RESULT2STR = [
      'PASS',
      'FAIL',
      'SKIP',
      'NOTRUN',
      'CRASH',
      'TIMEOUT',
      'MISSING',
      'LEAK',
      'SLOW',
      'TEXT',
      'AUDIO',
      'IMAGE',
      'IMAGETEXT',
      'REBASELINE',
      'NEEDSREBASELINE',
      'NEEDSMANUALREBASELINE',
  ]

  # This is used as an argument to struct.pack to implement the first four
  # fields in the struct layout described above (up to number of actual
  # results).  The array of actual results is append with a format of
  # '<n>B', where <n> is the number of actual results.
  TEST_PACK_FORMAT = '>IfBB'
  TEST_PACK_FORMAT_SIZE = struct.calcsize(TEST_PACK_FORMAT)

  master = ndb.StringProperty('m')
  builder_name = ndb.StringProperty('b')
  build_number = ndb.IntegerProperty('n')
  test_type = ndb.StringProperty('tp')
  blink_revision = ndb.StringProperty('br')
  chromium_revision = ndb.StringProperty('cr')
  version = ndb.IntegerProperty('v')
  time = ndb.DateTimeProperty('t')
  tests = ndb.BlobProperty('r')


  @classmethod
  def _encodeTests(cls, test_json):
    result = ''
    for test_name, test_result in test_json.iteritems():
      try:
        test_name_key = TestName.getKey(test_name)
      except:  # pragma: no cover
        logging.error('Could not get global key for test name %s', test_name)
        raise
      try:
        expected = cls.STR2RESULT[test_result['expected']]
        actual = tuple(
            [cls.STR2RESULT[a] for a in test_result['actual'].split()][:255])
        elapsed = float(test_result['time'])
      except:  # pragma: no cover
        logging.error('Could not parse numeric values from test result json')
        raise
      try:
        result += struct.pack(
            cls.TEST_PACK_FORMAT, test_name_key, elapsed, expected, len(actual))
        result += struct.pack('%dB' % len(actual), *actual)
      except:  # pragma: no cover
        logging.error('Could not struct pack test result')
        raise
    return result

  def _decodeTests(self):
    results = {}
    failures = [0] * len(self.RESULT2STR)
    i = 0
    while i + self.TEST_PACK_FORMAT_SIZE < len(self.tests):
      test_name_key, elapsed, expected, num_actual = struct.unpack(
          self.TEST_PACK_FORMAT, self.tests[i:i+self.TEST_PACK_FORMAT_SIZE])
      i += self.TEST_PACK_FORMAT_SIZE
      assert i + num_actual <= len(self.tests)
      test_name = TestName.getTestName(test_name_key)
      actual = struct.unpack('%dB' % num_actual, self.tests[i:i+num_actual])
      i += num_actual
      for a in actual:
        failures[a] += 1
      results[str(test_name)] = {
          'expected': self.RESULT2STR[expected],
          'actual': ' '.join([self.RESULT2STR[a] for a in actual]),
          'time': str(elapsed)
      }
    assert i == len(self.tests)
    return results, failures

  @classmethod
  def fromJson(cls, master, test_type, data):
    """Instantiate a new StepResult from parsed json.

    The expected json schema is what full-results.json contains. Note that the
    returned StepResult instance has NOT been saved to the datastore.
    """
    return cls(
        master=master,
        builder_name=data['builder_name'],
        build_number=int(data['build_number']),
        test_type=test_type,
        blink_revision=data['blink_revision'],
        chromium_revision=data['chromium_revision'],
        version=int(data['version']),
        time=datetime.utcfromtimestamp(float(data['seconds_since_epoch'])),
        tests=cls._encodeTests(data['tests']),
    )

  def toJson(self):
    """Convert a StepResult object to parsed json.

    The json schema is the same as what full-results.json contains.
    """
    tests, failures = self._decodeTests()
    failures = dict(zip(self.RESULT2STR, failures))
    data = {
        'builder_name': self.builder_name,
        'build_number': str(self.build_number),
        'blink_revision': self.blink_revision,
        'chromium_revision': self.chromium_revision,
        'version': str(self.version),
        'seconds_since_epoch': str(calendar.timegm(self.time.utctimetuple())),
        'tests': tests,
        'num_failures_by_type': failures
    }
    return (self.master, self.test_type, data)

  @classmethod
  def fromTestFile(cls, test_file):
    """Convert a TestFile object to a StepResult object.

    The returned StepResult has NOT been saved to the datastore.
    """
    if not test_file.data:
      test_file.load_data() #  pragma: no cover
    j = JsonResults.load_json(test_file.data)
    return cls.fromJson(test_file.master, test_file.test_type, j)
