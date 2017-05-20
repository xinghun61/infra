# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This recipe builds and packages third party software, such as Git."""

import json
import re

from recipe_engine import recipe_api


DEPS = [
  'depot_tools/cipd',
  'depot_tools/git',
  'depot_tools/gitiles',
  'build/file',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/shutil',
  'recipe_engine/step',
  'recipe_engine/url',
]

CPYTHON_REPO_URL = (
    'https://chromium.googlesource.com/external/github.com/python/cpython')
CPYTHON_PACKAGE_PREFIX = 'infra/python/cpython/'

# This version suffix serves to distinguish different revisions of Python built
# with this recipe.
CPYTHON_PACKAGE_VERSION_SUFFIX = '.chromium'

GIT_REPO_URL = (
    'https://chromium.googlesource.com/external/github.com/git/git')
GIT_PACKAGE_PREFIX = 'infra/git/'
# A regex for a name of the release asset to package, available at
# https://github.com/git-for-windows/git/releases
GIT_FOR_WINDOWS_ASSET_RES = {
  32: re.compile(r'^PortableGit-(\d+(\.\d+)*)-32-bit\.7z\.exe$'),
  64: re.compile(r'^PortableGit-(\d+(\.\d+)*)-64-bit\.7z\.exe$'),
}

# This version suffix serves to distinguish different revisions of git built
# with this recipe.
GIT_PACKAGE_VERSION_SUFFIX = '.chromium2'


def RunSteps(api):
  api.cipd.set_service_account_credentials(
      api.cipd.default_bot_service_account_credentials)
  with api.step.defer_results():
    if not api.platform.is_win:
      with api.step.nest('python'):
        PackagePythonForUnix(api)
    with api.step.nest('git'):
      PackageGit(api)


@recipe_api.composite_step
def PackagePythonForUnix(api):
  """Builds Python for Unix and uploads it to CIPD."""

  workdir = api.path['start_dir'].join('python')

  def install_openssl(workdir, sources, prefix):
    archive = sources.join('openssl-1.1.0e.tar.gz')
    with api.context(cwd=workdir):
      api.step('extract', ['tar', '-xzf', archive])

    build = workdir.join('openssl-1.1.0e')
    with api.context(cwd=build):
      target = {
        ('mac', 'intel', 64): 'darwin64-x86_64-cc',
        ('linux', 'intel', 32): 'linux-x86',
        ('linux', 'intel', 64): 'linux-x86_64',
      }[(api.platform.name, api.platform.arch, api.platform.bits)]

      api.step('configure', [
        build.join('Configure'),
        '--prefix=%s' % (prefix,),
        target,
      ])
      api.step('make', ['make', 'install'])

  def install_generic(name, workdir, archive, prefix):
    with api.context(cwd=workdir):
      api.step('extract', ['tar', '-xzf', archive])

    build = workdir.join(name)
    with api.context(cwd=build):
      api.step('configure', [
        build.join('configure'),
        '--prefix=%s' % (prefix,),
      ])
      api.step('make', ['make', 'install'])

  tag = GetLatestReleaseTag(api, CPYTHON_REPO_URL, 'v2.')
  version = tag.lstrip('v') + CPYTHON_PACKAGE_VERSION_SUFFIX
  workdir = api.path['start_dir'].join('python')
  api.file.rmtree('rmtree workdir', workdir)

  def install(target_dir):
    # cwd is Python checkout.
    sources = workdir.join('sources')
    api.cipd.ensure(sources, {
      'infra/third_party/source/openssl': 'version:1.1.0e',
      'infra/third_party/source/readline': 'version:7.0',
      'infra/third_party/source/termcap': 'version:1.3.1',
      'infra/third_party/source/zlib': 'version:1.2.11',
    })

    # Some systems (e.g., Mac OSX) don't actually offer these libraries by
    # default, or have incorrect or inconsistent library versions. We explicitly
    # install and use controlled versions of these libraries for a more
    # controlled, consistent, and (in case of OpenSSL) secure Python build.
    support_prefix = workdir.join('support_prefix')
    with api.step.nest('openssl'):
      install_openssl(workdir, sources, support_prefix)
    for name in ('readline-7.0', 'termcap-1.3.1', 'zlib-1.2.11'):
      with api.step.nest(name):
        install_generic(
            name,
            workdir,
            sources.join('%s.tar.gz' % (name,)),
            support_prefix)

    support_lib = support_prefix.join('lib')
    support_include = support_prefix.join('include')

    cflags = [
      '-I%s' % (support_include,),
    ]
    ldflags = [
      '-L%s' % (support_lib,),
    ]

    configure_env = {
      'CPPFLAGS': ' '.join(cflags),
      'LDFLAGS':  ' '.join(ldflags)
    }
    configure_flags = [
      '--disable-shared',
      '--prefix', target_dir,
    ]

    if api.platform.is_mac:
      configure_env.update({
        # The "getentropy" function is declared in Mac headers, but is not
        # actually available. This confuses the configuration script. Override
        # its automatic detection and force this to no ("n").
        'ac_cv_func_getentropy': 'n',
      })
    else:
      configure_flags += [
        # TODO: This breaks building on Mac builder, producing:
        #
        # *** WARNING: renaming "_struct" since importing it failed:
        # dlopen(build/lib.macosx-10.6-x86_64-2.7/_struct.so, 2): Symbol not
        # found: _PyExc_DeprecationWarning
        #
        # Maybe look into this if we have time later.
        '--enable-optimizations',
      ]

    # cwd is source checkout
    with api.context(env=configure_env):
      api.step('configure', ['./configure'] + configure_flags)

    # Edit the modules configuration to statically compile all Python modules.
    #
    # We do this by identifying the line '#*shared*' in "/Modules/Setup.dist"
    # and replacing it with '*static*'.
    setup_local = [
      '*static*',
      'SP=%s' % (support_prefix,),
      '_hashlib _hashopenssl.c -I$(SP)/include -I$(SP)/include/openssl '
          '$(SP)/lib/libssl.a $(SP)/lib/libcrypto.a',
      '_ssl _ssl.c -DUSE_SSL -I$(SP)/include -I$(SP)/include/openssl '
          '$(SP)/lib/libssl.a $(SP)/lib/libcrypto.a',
      'binascii binascii.c -I$(SP)/include $(SP)/lib/libz.a',
      'zlib zlibmodule.c -I$(SP)/include $(SP)/lib/libz.a',
      'readline readline.c -I$(SP)/include '
          '$(SP)/lib/libreadline.a $(SP)/lib/libtermcap.a',

      # Required: terminal newline.
      '',
    ]
    api.shutil.write(
        'Configure static modules',
        api.context.cwd.join('Modules', 'Setup.local'),
        '\n'.join(setup_local),
    )
    api.step.active_result.presentation.logs['Setup.local'] = setup_local

    # Build Python.
    api.step('make', ['make', 'install'])

  base_env = {}
  if api.platform.is_mac:
    base_env['MACOSX_DEPLOYMENT_TARGET'] = '10.6'

  with api.context(env=base_env):
    EnsurePackage(
        api,
        workdir,
        CPYTHON_REPO_URL,
        CPYTHON_PACKAGE_PREFIX,
        install,
        tag,
        version,
    )


@recipe_api.composite_step
def PackageGit(api):
  workdir = api.path['start_dir'].join('git')
  api.file.rmtree('rmtree workdir', workdir)
  if api.platform.is_win:
    PackageGitForWindows(api, workdir)
  else:
    PackageGitForUnix(api, workdir)


def PackageGitForUnix(api, workdir):
  """Builds Git on Unix and uploads it to a CIPD server."""

  def install_autoconf(source, prefix):
    with api.context(cwd=workdir):
      api.step('extract', ['tar', '-xzf', source.join('autoconf-2.69.tar.gz')])

    base = workdir.join('autoconf-2.69')
    with api.context(cwd=base):
      api.step(
          'configure',
          ['./configure', '--prefix', prefix])
      api.step(
          'install',
          ['make', 'install'])

  def install(target_dir):
    source = workdir.join('source')
    api.cipd.ensure(source, {
        'infra/third_party/source/autoconf': 'version:2.69',
    })

    # Note on OS X:
    # `make configure` requires autoconf in $PATH, which is not available on
    # OS X out of box. Unfortunately autoconf is not easy to make portable, so
    # we cannot package it.
    support_prefix = workdir.join('prefix')
    with api.step.nest('autoconf'):
      install_autoconf(source, support_prefix)
    support_bin = support_prefix.join('bin')

    # cwd is source checkout
    env = {
        # Set NO_INSTALL_HARDLINKS to avoid hard links in
        # <target_dir>/libexec/git-core/git-*
        # because CIPD does not support them. Use symlinks instead.
        'NO_INSTALL_HARDLINKS': 'VAR_PRESENT',
        'PATH': api.path.pathsep.join([str(support_bin), '%(PATH)s']),
    }
    with api.context(env=env):
      api.step('make configure', ['make', 'configure'])
      api.step('configure', ['./configure', '--prefix', target_dir])
      api.step('make install', ['make', 'install'])

  tag = api.properties.get('git_release_tag')
  if not tag:
    tag = GetLatestReleaseTag(api, GIT_REPO_URL, 'v')
  version = tag.lstrip('v') + GIT_PACKAGE_VERSION_SUFFIX
  EnsurePackage(
      api,
      workdir,
      GIT_REPO_URL,
      GIT_PACKAGE_PREFIX,
      install,
      tag,
      version,
  )


def PackageGitForWindows(api, workdir):
  """Repackages Git for Windows to CIPD."""
  # Get the latest release.
  version, archive_url = GetLatestGitForWindowsRelease(api)

  # Search for an existing CIPD package.
  package_name = GIT_PACKAGE_PREFIX + api.cipd.platform_suffix()
  if DoesPackageExist(api, package_name, version):
    api.python.succeeding_step('Synced', 'Package is up to date.')
    return

  # Download the archive.
  api.file.makedirs('ensure workdir', workdir)
  archive_path = workdir.join('archive.sfx')
  api.url.get_file(
      archive_url,
      archive_path,
      step_name='fetch archive',
      headers={
        'Accept': 'application/octet-stream',
      })

  # Extract the archive using 7z.exe.
  # In v2.12.2.2 there is as bug in the released self-extracting archive that
  # prevents extracting the archive from command line.
  seven_z_dir = workdir.join('7z')
  api.cipd.ensure(seven_z_dir, {
    'infra/7z/${platform}': 'version:9.20',
  })
  package_dir = workdir.join('package')
  api.step(
      'extract archive',
      [
        seven_z_dir.join('7z.exe'),
        'x', str(archive_path),
        '-o%s' % package_dir,
        '-y',  # Yes to all questions.
      ])

  # TODO(iannucci): move this whole extraction/packaging logic to a separate
  # resource script so that it can be run locally.

  # 7z.exe does not support "RunProgram" installation header, which specifies
  # the script to run after extraction. If the downloaded exe worked, it would
  # run the post-install script. Here we hard-code the name of the file to run
  # instead of extracting it from the downloaded archive because we already have
  # to know too much about it (see below), so we have to break the API boundary
  # anyway.
  with api.context(cwd=package_dir):
    api.step(
      'post-install',
      [
        package_dir.join('git-bash.exe'),
        '--no-needs-console',
        '--hide',
        '--no-cd',
        '--command=post-install.bat',
      ],
      # We expect exit code 1. The post-script.bat tries to delete itself in the
      # end and it always causes a non-zero exit code.
      #
      # Note that the post-install.bat also ignores exit codes of the *.post
      # scripts that it runs, which is the important part.
      # This has been the case for at least 2yrs
      # https://github.com/git-for-windows/build-extra/commit/f1962c881ab18dd1ade087d2f5a7cac5b976f624
      #
      # BUG: https://github.com/git-for-windows/git/issues/1147
      ok_ret=(1,))

    # Change the package gitconfig defaults to match what chromium expects, and
    # enable various performance tweaks.
    settings = [
      ('core.autocrlf', 'false'),
      ('core.filemode', 'false'),
      ('core.preloadindex', 'true'),
      ('core.fscache', 'true'),
    ]
    # e.g. mingw32/etc/gitconfig
    unpacked_gitconfig = package_dir.join(
      'mingw%d' % api.platform.bits, 'etc', 'gitconfig')
    for setting, value in settings:
      api.step(
        'tweak %s=%s' % (setting, value),
        [
          package_dir.join('cmd', 'git.exe'),
          'config',
          '-f', unpacked_gitconfig,
          setting, value,
        ]
      )

    api.file.copy(
      'install etc/profile.d/python.sh',
      api.resource('profile.d.python.sh'),
      package_dir.join('etc', 'profile.d', 'python.sh'))

    api.file.copy(
      'install etc/profile.d/vpython.sh',
      api.resource('profile.d.vpython.sh'),
      package_dir.join('etc', 'profile.d', 'vpython.sh'))

  CreatePackage(api, package_name, workdir, package_dir, version)


def GetLatestGitForWindowsRelease(api):
  """Returns a tuple (version, archive_url) for the latest release.

  Raises a StepFailure if a suitable release is not found.
  """
  # API docs:
  # https://developer.github.com/v3/repos/releases/#get-the-latest-release
  latest_release = api.url.get_json(
      'https://api.github.com/repos/git-for-windows/git/releases/latest',
      step_name='get latest release').output
  if not latest_release:  # pragma: no cover
    raise api.step.StepFailure('latest release of Git for Windows is not found')

  asset = None
  version = None
  for a in latest_release['assets']:
    m = GIT_FOR_WINDOWS_ASSET_RES[api.platform.bits].match(str(a['name']))
    if not m:
      continue
    if asset is not None:  # pragma: no cover
      raise api.step.StepFailure(
          'multiple suitable git release assets: %s and %s' %
          (a['name'], asset['name']))
    asset = a
    version = m.group(1)
  if not asset:  # pragma: no cover
    raise api.step.StepFailure('could not find suitable asset')
  version += GIT_PACKAGE_VERSION_SUFFIX
  return version, asset['url']


def EnsurePackage(
    api, workdir, repo_url, package_name_prefix, install, tag, version):
  """Ensures that the specified CIPD package exists."""
  package_name = package_name_prefix + api.cipd.platform_suffix()

  # Check if the package already exists.
  if DoesPackageExist(api, package_name, version):
    api.python.succeeding_step('Synced', 'Package is up to date.')
    return

  # Fetch source code and build.
  checkout_dir = workdir.join('checkout')
  package_dir = workdir.join('package')
  api.git.checkout(
      repo_url, ref='refs/tags/' + tag, dir_path=checkout_dir,
      submodules=False)
  with api.context(cwd=checkout_dir):
    install(package_dir)

  CreatePackage(api, package_name, workdir, package_dir, version)


def CreatePackage(api, name, workdir, root, version):
  package_file = workdir.join('package.cipd')
  api.cipd.build(root, package_file, name)
  api.cipd.register(name, package_file, tags={'version': version})


def DoesPackageExist(api, name, version):
  search = api.cipd.search(name, 'version:' + version)
  return bool(search.json.output['result'])


def GetLatestReleaseTag(api, repo_url, prefix='v'):
  result = None
  result_parsed = None
  tag_prefix = 'refs/tags/'
  for ref in api.gitiles.refs(repo_url):
    if not ref.startswith(tag_prefix):
      continue
    t = ref[len(tag_prefix):]

    # Parse version.
    if not t.startswith(prefix):
      continue
    parts = t[len(prefix):].split('.')
    if not all(p.isdigit() for p in parts):
      continue
    parsed = map(int, parts)

    # Is it the latest?
    if result_parsed is None or result_parsed < parsed:
      result = t
      result_parsed = parsed
  return result


def GenTests(api):
  python_test_refs = api.gitiles.make_refs_test_data(
      'HEAD',
      'refs/heads/master',
      'refs/tags/not-a-version',
      'refs/tags/v2.1.1',
      'refs/tags/v2.1.2',
      'refs/tags/v2.1.3rc1',
      'refs/tags/v3.0.0',
  )
  git_test_refs = api.gitiles.make_refs_test_data(
      'HEAD',
      'refs/heads/master',
      'refs/tags/not-a-version',
      'refs/tags/v2.1.1',
      'refs/tags/v2.1.2',
      'refs/tags/v2.1.3rc1',
      'refs/tags/v2.12.2.2',
  )
  git_for_windows_release = {
    'assets': [
      {
        'url': (
            'https://api.github.com/repos/git-for-windows/git/releases/assets/'
            '3580732'),
        'name': 'PortableGit-2.12.2.2-32-bit.7z.exe',
      },
      {
        'url': (
            'https://api.github.com/repos/git-for-windows/git/releases/assets/'
            '3580733'),
        'name': 'PortableGit-2.12.2.2-64-bit.7z.exe',
      },
    ]
  }
  platforms = (
    ('linux', 64, 'linux-amd64'),
    ('linux', 32, 'linux-386'),
    ('mac', 64, 'mac-amd64'),
    ('win', 64, 'windows-amd64'),
    ('win', 32, 'windows-386'),
  )
  def GenTest(platform_name, bits, platform_suffix, new_package):
    cpython_package_name = CPYTHON_PACKAGE_PREFIX + platform_suffix
    git_package_name = GIT_PACKAGE_PREFIX + platform_suffix
    test = (
        api.test('new_%s_on_%s' % (new_package, platform_suffix)) +
        api.platform.name(platform_name) +
        api.platform.bits(bits) +
        api.override_step_data(
            'git.cipd search %s version:2.12.2.2%s' % (
              git_package_name, GIT_PACKAGE_VERSION_SUFFIX),
            api.cipd.example_search(
                git_package_name,
                instances=bool(new_package != 'git')))
    )
    if platform_name != 'win':
      test += api.step_data('git.refs', git_test_refs)
      test += api.step_data('python.refs', python_test_refs)
      test += api.override_step_data(
          'python.cipd search %s version:2.1.2%s' % (
            cpython_package_name, CPYTHON_PACKAGE_VERSION_SUFFIX),
          api.cipd.example_search(
              cpython_package_name,
              instances=bool(new_package != 'python')))
    else:
      test += api.url.json(
          'git.get latest release',
          git_for_windows_release)
      if new_package == 'git':
        test += api.step_data('git.post-install', retcode=1)
    return test

  for (platform_name, bits, platform_suffix) in platforms:
    for new_package in ('python', 'git'):
      yield GenTest(platform_name, bits, platform_suffix, new_package)

  yield (
      api.test('mac_failure') +
      GenTest('mac', 64, 'mac-amd64', 'python') +
      api.step_data('python.make', retcode=1)
  )

  yield (
      api.test('mac_specific_git_tag') +
      api.platform.name('mac') +
      api.platform.bits(64) +
      api.properties(git_release_tag='v2.12.2') +
      api.step_data('python.refs', python_test_refs)
  )
