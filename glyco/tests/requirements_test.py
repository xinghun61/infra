# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import textwrap
import unittest

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'third_party'))

from glucose.requirements import parse_requirements, Requirements


class ParseRequirementsTest(unittest.TestCase):
  def test_empty_file(self):
    reqs = parse_requirements('')
    self.assertEqual(reqs, [])

  def test_one_package(self):
    content = textwrap.dedent("""\
    mypackage == 1.0
    """)
    reqs = parse_requirements(content)
    self.assertEqual(len(reqs), 1)
    for req in reqs:
      self.assertIsInstance(req, Requirements)
    self.assertEqual(reqs[0].package_name, 'mypackage')
    self.assertEqual(reqs[0].version, '1.0')
    self.assertEqual(reqs[0].hashes, ())

  def test_one_package_no_spaces(self):
    content = textwrap.dedent("""\
    mypackage==1.0
    """)
    reqs = parse_requirements(content)
    self.assertEqual(len(reqs), 1)
    for req in reqs:
      self.assertIsInstance(req, Requirements)
    self.assertEqual(reqs[0].package_name, 'mypackage')
    self.assertEqual(reqs[0].version, '1.0')
    self.assertEqual(reqs[0].hashes, ())

  def test_one_package_with_one_hash(self):
    content = textwrap.dedent("""\
    # sha1: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef
    mypackage==1.0
    """)
    reqs = parse_requirements(content)
    self.assertEqual(len(reqs), 1)
    for req in reqs:
      self.assertIsInstance(req, Requirements)
    self.assertEqual(reqs[0].package_name, 'mypackage')
    self.assertEqual(reqs[0].version, '1.0')
    self.assertEqual(reqs[0].hashes,
                     (('sha1', 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef'),))

  def test_one_package_with_two_hashes(self):
    content = textwrap.dedent("""\
    # sha1: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef
    # sha1: 1234567812345678123456781234567812345678
    mypackage==1.0
    """)
    reqs = parse_requirements(content)
    self.assertEqual(len(reqs), 1)
    for req in reqs:
      self.assertIsInstance(req, Requirements)
    self.assertEqual(reqs[0].package_name, 'mypackage')
    self.assertEqual(reqs[0].version, '1.0')
    self.assertEqual(reqs[0].hashes,
                     (('sha1', 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef'),
                      ('sha1', '1234567812345678123456781234567812345678')))

  def test_one_package_two_hashes_and_blank_line(self):
    content = textwrap.dedent("""\
    # sha1: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef

    # sha1: 1234567812345678123456781234567812345678
    mypackage==1.0
    """)
    reqs = parse_requirements(content)
    self.assertEqual(len(reqs), 1)
    for req in reqs:
      self.assertIsInstance(req, Requirements)
    self.assertEqual(reqs[0].package_name, 'mypackage')
    self.assertEqual(reqs[0].version, '1.0')
    self.assertEqual(reqs[0].hashes,
                     (('sha1', '1234567812345678123456781234567812345678'),))

  def test_one_package_two_hashes_and_comment_line(self):
    content = textwrap.dedent("""\
    # linux
    # sha1: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef
    # windows
    # sha1: 1234567812345678123456781234567812345678
    mypackage==1.0
    """)
    reqs = parse_requirements(content)
    self.assertEqual(len(reqs), 1)
    for req in reqs:
      self.assertIsInstance(req, Requirements)

    self.assertEqual(reqs[0].package_name, 'mypackage')
    self.assertEqual(reqs[0].version, '1.0')
    self.assertEqual(reqs[0].hashes,
                     (('sha1', 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef'),
                      ('sha1', '1234567812345678123456781234567812345678')))

  def test_two_packages_with_hashes(self):
    content = textwrap.dedent("""\
    # sha1: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef
    mypackage == 1.0

    # sha1: 1234567812345678123456781234567812345678
    myotherpackage == 2.0
    """)
    reqs = parse_requirements(content)
    self.assertEqual(len(reqs), 2)
    for req in reqs:
      self.assertIsInstance(req, Requirements)
    self.assertEqual(reqs[0].package_name, 'mypackage')
    self.assertEqual(reqs[0].version, '1.0')
    self.assertEqual(reqs[0].hashes,
                     (('sha1', 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef'),))

    self.assertEqual(reqs[1].package_name, 'myotherpackage')
    self.assertEqual(reqs[1].version, '2.0')
    self.assertEqual(reqs[1].hashes,
                     (('sha1', '1234567812345678123456781234567812345678'),))


if __name__ == '__main__':
  unittest.main()
