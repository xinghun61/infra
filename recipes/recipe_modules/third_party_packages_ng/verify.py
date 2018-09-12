# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Logic to run testing script on the built CIPD package."""

from . import run_script

def run_test(api, workdir, spec, cipd_spec):
  """Runs the test in the Verify message on the CIPD package.

  Args:
    * workdir (Workdir) - The directories that we're currently operating within.
    * spec (ResolvedSpec) - The spec for the package we're testing.
    * cipd_spec (CIPDSpec) - The package we've already built and want to test.
  """
  script = spec.create_pb.verify.test[0]
  rest = spec.create_pb.verify.test[1:] + [cipd_spec.local_pkg_path()]
  run_script.run_script(api, workdir.script_dir(spec.name).join(script), *rest)
