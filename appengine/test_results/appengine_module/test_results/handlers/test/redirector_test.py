# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from appengine_module.test_results.handlers import redirector

class RedirectorTest(unittest.TestCase):

  def test_url_from_commit_positions(self):
    def mock_load_url(url):
      if url == 'https://cr-rev.appspot.com/_ah/api/crrev/v1/redirect/1':
        git_sha = 'aaaaaaa'
      else:
        git_sha = 'bbbbbbb'
      return '''{
 "git_sha": "%s",
 "repo": "chromium/src",
 "redirect_url": "https://chromium.googlesource.com/chromium/src/+/%s",
 "project": "chromium",
 "redirect_type": "GIT_FROM_NUMBER",
 "repo_url": "https://chromium.googlesource.com/chromium/src/",
 "kind": "crrev#redirectItem",
 "etag": "\\\"vOastG91kaV9uxC3-P-4NolRM6s/U8-bHfeejPZOn0ELRGhed-nrIX4\\\""
}''' % (git_sha, git_sha)

    old_load_url = redirector.load_url
    try:
      redirector.load_url = mock_load_url

      expected = ('https://chromium.googlesource.com/chromium/src/+log/'
        'aaaaaaa^..bbbbbbb?pretty=fuller')
      self.assertEqual(redirector.url_from_commit_positions(1, 2), expected)
    finally:
      redirector.load_url = old_load_url
