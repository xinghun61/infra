# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
  "recipe_engine/file",
  "recipe_engine/path",
  "recipe_engine/platform",
  "recipe_engine/properties",

  "third_party_packages_ng",
]

PROPERTIES = {
  'GOOS': Property(),
  'GOARCH': Property(),
  'load_dupe': Property(kind=bool, default=False),
}

def RunSteps(api, GOOS, GOARCH, load_dupe):
  builder = api.path['cache'].join('builder')

  # do a checkout in `builder`
  api.third_party_packages_ng.load_packages_from_path(
    builder.join('package_repo'))

  # doing it twice should raise a DuplicatePackage exception
  if load_dupe:
    api.third_party_packages_ng.load_packages_from_path(
      builder.join('dup_repo'))

  _, unsupported = api.third_party_packages_ng.ensure_uploaded(
    platform='%s-%s' % (GOOS, GOARCH))

  excluded = {'unsupported'}
  if api.platform.is_win:
    excluded.add('posix_tool')
  assert unsupported == excluded, "unexpected: %r" % (unsupported,)

def GenTests(api):
  pkgs = sorted({
    'tool': '''
    create {
      source {
        git {
          repo: "https://go.repo/tool"
          tag_pattern: "v%s"
          version_join: "-"
          patch_dir: "patches"
        }
        subdir: "src/go.repo/tool"
        patch_version: "chops.1"
      }
      build {
        # We use an older version of the tool to bootstrap new versions.
        tool: "tool@0.9.0"
      }
      package {
        version_file: ".versions/tool.cipd_version"
      }
      build {
        install: "install.sh"
        install: "intel"
      }
    }

    create {
      platform_re: "mac-.*"
      build {
        install: "install-mac.h"
      }
      package {
        install_mode: symlink
      }
      verify {
        test: "test.py"
        test: "mac"
      }
    }

    create {
      platform_re: "windows-.*"
      verify {
        test: "test.py"
        test: "windows"
      }
    }

    create {
      platform_re: "linux-.*"
      verify {
        test: "test.py"
        test: "linux"
      }
    }

    create {
      platform_re: "linux-arm.*"
      build {
        install: "install.sh"
        install: "arm"
      }
    }

    upload { pkg_prefix: "prefix/build_tools" }
    ''',

    'dep': '''
    create {
      source { cipd {pkg: "source/dep" default_version: "1.0.0"} }
      build {
        tool: "tool"
      }
    }
    upload { pkg_prefix: "prefix/deps" }
    ''',

    'pkg': '''
    create {
      source { script { name: "fetch.py" } }
      build {
        tool: "tool"
        dep:  "dep"
      }
    }
    upload { pkg_prefix: "prefix/tools" }
    ''',

    'unsupported': '''
    create { unsupported: true }
    ''',

    'posix_tool': '''
    create {
      platform_re: "linux-.*|mac-.*"
      source {
        cipd { pkg: "source/posix_tool" default_version: "1.2.0" }
        unpack_archive: true
      }
      build {}  # default build options
    }
    upload { pkg_prefix: "tools" }
    ''',
  }.items())


  for goos, goarch in (('linux', 'amd64'),
                       ('linux', 'armv6l'),
                       ('windows', 'amd64'),
                       ('mac', 'amd64')):
    plat_name = 'win' if goos == 'windows' else goos

    sep = '\\' if goos == 'windows' else '/'
    pkg_repo_path = sep.join(
      ['[CACHE]', 'builder', 'package_repo', '%s', '3pp.pb'])

    test = (api.test('integration_test_%s-%s' % (goos, goarch))
      + api.platform(plat_name, 64)  # assume all hosts are 64 bits.
      + api.properties(GOOS=goos, GOARCH=goarch)
      + api.step_data('find package specs',
                      api.file.glob_paths([
                        pkg_repo_path % name for name, _ in pkgs]))
    )
    for pkg, spec in pkgs:
      test += api.step_data("load package specs.read '%s'" % pkg,
                            api.file.read_text(spec))
    yield test

  yield (api.test('empty spec')
      + api.properties(GOOS='linux', GOARCH='amd64')
      + api.step_data(
          'find package specs',
          api.file.glob_paths(['[CACHE]/builder/package_repo/bad/3pp.pb']))
  )

  yield (api.test('bad spec')
      + api.properties(GOOS='linux', GOARCH='amd64')
      + api.step_data(
          'find package specs',
          api.file.glob_paths(['[CACHE]/builder/package_repo/bad/3pp.pb']))
      + api.step_data(
          "load package specs.read 'bad'", api.file.read_text('narwhal'))
      + api.expect_exception('BadParse')
  )

  yield (api.test('duplicate load')
      + api.properties(GOOS='linux', GOARCH='amd64', load_dupe=True)
      + api.step_data(
          'find package specs',
          api.file.glob_paths(['[CACHE]/path/something/3pp.pb']))
      + api.step_data(
          "load package specs.read 'something'",
          api.file.read_text('create {}'))
      + api.step_data(
          'find package specs (2)',
          api.file.glob_paths(['[CACHE]/path/something/3pp.pb']))
      + api.expect_exception('DuplicatePackage')
  )
