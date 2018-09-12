# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from .cipd_spec import CIPDSpec


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

  @property
  def name(self):
    """The name of the package."""
    return self._name

  @property
  def base_path(self):
    """Path to the directory containing the package folders.

    This will be one of the paths passed to `load_packages_from_path`.
    """
    return self._base_path

  @property
  def tool_platform(self):
    """The CIPD platform name for tools to build this ResolvedSpec.

    USUALLY, this is equivalent to the host platform (the machine running the
    recipe), but in the case of cross-compilation for linux, this will be the
    platform of the cross-compile docker container (i.e. 'linux-amd64').

    This is used to build programs that are used during the compilation of the
    package (e.g. `cmake`, `ninja`, etc.).
    """
    return tool_platform(self._api, self._platform, self._spec_pb)

  @staticmethod
  def _assert_resolve_for(condition):
    assert condition, 'Impossible; _resolve_for should have caught this'

  @property
  def create_pb(self):
    """The singular `spec_pb2.Spec.Create` message."""
    self._assert_resolve_for(len(self._spec_pb.create) == 1)
    return self._spec_pb.create[0]

  @property
  def upload_pb(self):
    """The `spec_pb2.Spec.Upload` message."""
    return self._spec_pb.upload

  @property
  def source_method(self):
    """A tuple of (source_method_name, source_method_pb).

    These are the result of parsing the `method` field of the Spec.Create.Source
    message.
    """
    pb = self.create_pb.source
    method = pb.WhichOneof("method")
    self._assert_resolve_for(method is not None)
    self._assert_resolve_for(method in ('git', 'cipd', 'script'))
    return method, getattr(pb, method)

  @property
  def host_dir(self):
    """Path to the folder containing this spec on the host (i.e. not the
    version copied into the checkout)."""
    return self._base_path.join(self.name)

  @property
  def platform(self):
    """The CIPD platform that this ResolvedSpec was resolved for."""
    return self._platform

  @property
  def unpinned_tools(self):
    """The list of unpinned_tools as ResolvedSpec's.

    These packages must exist in order to build this ResolvedSpec, and may be
    implicitly built during the building of this ResolvedSpec.
    """
    return self._unpinned_tools

  @property
  def pinned_tool_info(self):
    """A generator of (package_name, version) for tools which this ResolvedSpec
    depends on, but which MUST ALREADY EXIST on the CIPD server.

    These will not be built implicitly when building this ResolvedSpec.
    """
    for t in self.create_pb.build.tool:
      name, version = parse_name_version(t)
      if version != 'latest':
        yield name, version

  @property
  def _all_possible_deps(self):
    """Yields all the package names that this ResolvedSpec depends on, which
    includes both `deps` and `tools`.

    Used internally by the __cmp__ function.

    Infinite recursion is prevented by the _resolve_for function (which
    constructs all of the ResolvedSpec instances).
    """
    for dep in self._deps:
      for subdep in dep._all_possible_deps:
        yield subdep
      yield dep
    # these are unpinned tools we may have to build.
    for tool in self._unpinned_tools:
      for subdep in tool._all_possible_deps:
        yield subdep
      yield tool

  def cipd_spec(self, version):
    """Returns a CIPDSpec object for the result of building this ResolvedSpec's
    package/platform/version.

    Args:
      * version (str) - The symver of this package to get the CIPDSpec for.
    """
    pkg_name = '%s/%s/%s' % (self.upload_pb.pkg_prefix,
                             self.name, self.platform)
    patch_ver = self.create_pb.source.patch_version
    symver = '%s%s' % (version, '.'+patch_ver if patch_ver else '')
    return CIPDSpec(self._api, pkg_name, symver)

  def __cmp__(self, other):
    """This allows ResolvedSpec's to be sorted.

    ResolvedSpec's which depend on another ResolvedSpec will sort after it.
    """
    if self is other: # pragma: no cover
      return 0

    # self < other if other depends on self, OR
    #              if other uses self as a tool
    if self in other._all_possible_deps:
      return -1

    # self > other if self depends on other, OR
    #              if self uses other as a tool
    if other in self._all_possible_deps:
      return 1

    # otherwise sort alphabetically
    return cmp(self.name, other.name)
