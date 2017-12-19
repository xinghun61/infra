# Copyright (c) 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

def DoNotContribute(output_api):
  return [output_api.PresubmitError(
      'Glyco is deprecated in favor of vpython, and barely used. '
      'Its tests are not part of CQ or CI. '
      'Please do not contribute to Glyco.'
  )]


def CheckChangeOnCommit(_input_api, output_api):
  return DoNotContribute(output_api)


def CheckChangeOnUpload(_input_api, output_api):
  return DoNotContribute(output_api)
