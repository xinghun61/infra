# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Operations for urls to builds."""
import urllib


def CreateBuildUrl(master_name, builder_name, build_number):
  """Creates the url for the given build."""
  builder_name = urllib.quote(builder_name)
  return 'https://ci.chromium.org/buildbot/%s/%s/%s' % (
      master_name, builder_name, build_number)
