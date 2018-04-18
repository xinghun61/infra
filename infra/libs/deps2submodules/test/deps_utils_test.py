# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap
import unittest

from infra.libs.deps2submodules import deps_utils

class DepsUtilsTest(unittest.TestCase):
  def testEvalSimple(self):
    content = textwrap.dedent("""
      vars = {
        'src': 'https://chromium.googlesource.com/chromium/src',
      }
      deps = {
        'fount/src': Var('src'),
      }
      """)
    return deps_utils.EvalDepsContent(content)

  def testEvalMissingVar(self):
    content = textwrap.dedent("""
      vars = {
        'src': 'https://chromium.googlesource.com/chromium/src',
      }
      deps = {
        'fount/src': Var('chromium'),
      }
      """)
    with self.assertRaises(Exception):
      deps_utils.EvalDepsContent(content)

  def testExtractUrlSimple(self):
    dep = 'https://chromium.googlesource.com/chromium/src'
    return deps_utils.ExtractUrl(dep)

  def testExtractUrlNested(self):
    dep = {
        'url': 'https://chromium.googlesource.com/chromium/src',
        'condition': 'always',
    }
    return deps_utils.ExtractUrl(dep)

  def testExtractUrlWeirdType(self):
    dep = 1732
    with self.assertRaises(Exception):
      deps_utils.ExtractUrl(dep)

  def testExtractUrlDictSansUrl(self):
    dep = {
        'condition': 'always',
    }
    with self.assertRaises(KeyError):
      deps_utils.ExtractUrl(dep)

  def testExtractUrlFiltered(self):
    dep = {
        'url': 'https://chromium.googlesource.com/chromium/src',
        'condition': 'checkout_google_internal',
    }
    self.assertIsNone(deps_utils.ExtractUrl(dep))
