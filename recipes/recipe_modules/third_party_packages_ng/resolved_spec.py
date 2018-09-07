# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


def parse_name_version(name_version):
  """Parses a package 'name', or 'name@version'.

  Returns (name, version). If the input was just 'name' then the version is
  'latest'.
  """
  if '@' in name_version:
    name, version = name_version.split('@')
  else:
    name, version = name_version, 'latest'
  return name, version


def platform_for_host(api):
  """This returns a cipd platform name for the current host, derived from the
  `platform` recipe_module.
  """
  return '%s-%s' % (
    {
      'win': 'windows',
      'linux': 'linux',  # not actually used, but for completeness
      'mac': 'mac',
    }[api.platform.name],
    {
      ('intel', 32): '386',
      ('intel', 64): 'amd64',
    }[api.platform.arch, api.platform.bits]
  )


def tool_platform(api, platform, _spec_pb):
  """Returns the target platform for tools needed to build the provided
  `platform`. E.g. if we're targetting `linux-x86` the toolchain might be
  `linux-amd64`, regardless of the host platform (because we use docker to build
  for linux-x86, and so the tools need to run in the docker container).

  When not cross-compiling, this returns a cipd platform name for the current
  host, derived from the `platform` recipe_module.
  """
  if platform.startswith('linux-'):
    # TODO(iannucci): When we can control the toolchains more precisely in
    # `spec_pb`, make this contingent on the selection of dockcross. Until
    # then, hardcode the dockcross host type.
    return 'linux-amd64'
  return platform_for_host(api)


class ResolvedSpec(object):
  """The ResolvedSpec represents a version of the Spec protobuf message, but
  resolved for a single target platform (e.g. "windows-amd64").

  It has helper methods and properties to read the resolved data.
  """
  def __init__(self, api, name, platform, base_path, spec, deps,
               unpinned_tools):
    self._api = api

    self._name = name                     # Name of the package
    self._platform = platform             # Platform resolved for
    # Path to the directory containing the package definition folder
    self._base_path = base_path
    self._spec_pb = spec                  # spec_pb2.Spec
    self._deps = deps                     # list[ResolvedSpec]
    self._unpinned_tools = unpinned_tools # list[ResolvedSpec]
