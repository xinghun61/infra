# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import run_script

def run_installation(api, workdir, spec):
  """Actually runs build phase of the given `spec` within the provided
  `workdir`.

  This function knows how to install the cross-compiler toolchain into the
  environment (if needed for the spec's target platform).

  Args:
    * api - The ThirdPartyPackagesNGApi's `self.m` module collection.
    * workdir (Workdir) - The working directory object we're going to build the
      spec in. This function will create the output in `workdir.output_prefix`.
    * spec (ResolvedSpec) - The spec to build.
  """
  api.file.ensure_directory('make output dir', workdir.output_prefix)
  my_args = [workdir.output_prefix, workdir.deps_prefix]
  if spec.create_pb.build.install:
    script = spec.create_pb.build.install[0]
    rest = spec.create_pb.build.install[1:] + my_args
  else:
    script = "install.sh"
    rest = my_args

  env_prefixes = {
    'PATH': [workdir.tools_prefix, workdir.tools_prefix.join('bin')]
  }
  with api.context(cwd=workdir.checkout, env_prefixes=env_prefixes):
    run_script.run_script(api, workdir.script_dir(spec.name).join(script),
                          *rest,
                          compile_platform=spec.platform, workdir=workdir)
