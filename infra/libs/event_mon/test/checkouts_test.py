# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
from infra.libs.event_mon import checkouts


class TestParseRevInfo(unittest.TestCase):
  def test_empty_file(self):
    self.assertEqual(checkouts.parse_revinfo(''), {})

  def test_one_checkout(self):
    self.assertEqual(checkouts.parse_revinfo('a: b@c'),
                     {'a': {'source_url': 'b', 'revision': 'c'}})

  def test_multiple_checkouts(self):
    self.assertEqual(checkouts.parse_revinfo('c: d@e\nf: g@h'),
                     {'c': {'source_url': 'd', 'revision': 'e'},
                      'f': {'source_url': 'g', 'revision': 'h'}})

  def test_missing_revision(self):
    self.assertEqual(checkouts.parse_revinfo('i: j'),
                     {'i': {'source_url': 'j', 'revision': None}})

  def test_on_actual_output(self):
    # pylint: disable=line-too-long
    output = """build: https://chromium.googlesource.com/chromium/tools/build.git@553752662e0dd4e135e6956d3f8aa9a02c3c1407
build/scripts/gsd_generate_index: svn://svn.chromium.org/chrome/trunk/tools/gsd_generate_index@293875
build/scripts/private/data/reliability: svn://svn.chromium.org/chrome/trunk/src/chrome/test/data/reliability@293875
build/scripts/tools/deps2git: svn://svn.chromium.org/chrome/trunk/tools/deps2git@293875
build/third_party/gsutil: svn://svn.chromium.org/gsutil/trunk/src@263
build/third_party/gsutil/boto: svn://svn.chromium.org/boto@7
build/third_party/lighttpd: svn://svn.chromium.org/chrome/trunk/deps/third_party/lighttpd@58968
build/third_party/xvfb: svn://svn.chromium.org/chrome/trunk/tools/third_party/xvfb@293875
depot_tools: svn://svn.chromium.org/chrome/trunk/tools/depot_tools@293875
expect_tests: https://chromium.googlesource.com/infra/testing/expect_tests.git@7a0649eb4fcfdf05ebfaffbc33752122a88d72f7
infra: https://chromium.googlesource.com/infra/infra.git@5e86c081d415509716a0ce1aa7a62b915b59aa03
infra/appengine/swarming: https://chromium.googlesource.com/infra/swarming.git@7a831b64ebff96260756e353ab002644d7c3abb6
infra/appengine/third_party/bootstrap: https://chromium.googlesource.com/infra/third_party/bootstrap.git@b4895a0d6dc493f17fe9092db4debe44182d42ac
infra/appengine/third_party/cloudstorage: https://chromium.googlesource.com/infra/third_party/cloudstorage.git@ad74316d12e198e0c7352bd666bbc2ec7938bd65
infra/appengine/third_party/endpoints-proto-datastore: https://chromium.googlesource.com/infra/third_party/endpoints-proto-datastore.git@971bca8e31a4ab0ec78b823add5a47394d78965a
infra/appengine/third_party/google-api-python-client: https://chromium.googlesource.com/external/github.com/google/google-api-python-client.git@49d45a6c3318b75e551c3022020f46c78655f365
infra/appengine/third_party/highlight: https://chromium.googlesource.com/infra/third_party/highlight.js.git@fa5bfec38aebd1415a81c9c674d0fde8ee5ef0ba
infra/appengine/third_party/npm_modules: https://chromium.googlesource.com/infra/third_party/npm_modules.git@f3f825ae2d3521d889fe076bd2229f6a1fadaac6
infra/appengine/third_party/pipeline: https://chromium.googlesource.com/infra/third_party/appengine-pipeline.git@e79945156a7a3a48eecb29b792a9b7925631aadf
infra/appengine/third_party/src/github.com/golang/oauth2: https://github.com/golang/oauth2.git@cb029f4c1f58850787981eefaf9d9bf547c1a722
infra/appengine/third_party/trace-viewer: https://chromium.googlesource.com/external/trace-viewer.git@76a4496033c164d8be9ee8c57f702b0859cb1911
infra/bootstrap/virtualenv: https://github.com/pypa/virtualenv.git@93cfa83481a1cb934eb14c946d33aef94c21bcb0
testing_support: https://chromium.googlesource.com/infra/testing/testing_support.git@134e350cb5c6bfc14e8b8d0f0f0508ffc769d3bb
    """
    revinfo = checkouts.parse_revinfo(output)
    # Check some invariants
    self.assertTrue(len(revinfo) > 0, 'revinfo should contain values')
    for v in revinfo.itervalues():
      self.assertEqual(len(v), 2)
      self.assertIn('://', v['source_url'],
                    msg='"://" not in url string. Got %s' % v['source_url'])
      self.assertIn(v['source_url'].split('://')[0], ('https', 'svn'))
