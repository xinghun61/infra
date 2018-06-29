# Copyright (c) 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


def CommonChecks(input_api, output_api):  # pragma: no cover
  return input_api.canned_checks.CheckPatchFormatted(
      input_api,
      output_api,
      check_python=True,
      result_factory=output_api.PresubmitError
  )


def CheckChangeOnUpload(input_api, output_api):  # pragma: no cover
  return CommonChecks(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):  # pragma: no cover
  return CommonChecks(input_api, output_api)
