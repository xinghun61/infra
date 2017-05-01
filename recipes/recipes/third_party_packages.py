# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This recipe builds and packages third party software, such as Git."""

import json
import re


DEPS = [
  'depot_tools/cipd',
  'depot_tools/git',
  'depot_tools/gitiles',
  'depot_tools/url',
  'build/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]

CPYTHON_REPO_URL = (
    'https://chromium.googlesource.com/external/github.com/python/cpython')
CPYTHON_PACKAGE_PREFIX = 'infra/python/cpython/'

GIT_REPO_URL = (
    'https://chromium.googlesource.com/external/github.com/git/git')
GIT_PACKAGE_PREFIX = 'infra/git/'
# A regex for a name of the release asset to package, available at
# https://github.com/git-for-windows/git/releases
GIT_FOR_WINDOWS_ASSET_RE = re.compile(
    r'^PortableGit-(\d+(\.\d+)*)-32-bit\.7z\.exe$')


def RunSteps(api):
  api.cipd.set_service_account_credentials(
      api.cipd.default_bot_service_account_credentials)
  if not api.platform.is_win:
    with api.step.nest('python'):
      PackagePythonForUnix(api)
  with api.step.nest('git'):
    PackageGit(api)


def PackagePythonForUnix(api):
  """Builds Python for Unix and uploads it to CIPD."""

  def install(target_dir):
    # cwd is source checkout
    api.step('configure', ['./configure'])
    api.step('make', ['make', 'install', 'prefix=%s' % target_dir])

  tag = GetLatestReleaseTag(api, CPYTHON_REPO_URL, 'v2.')
  version = tag.lstrip('v')
  workdir = api.path['start_dir'].join('python')
  api.file.rmtree('rmtree workdir', workdir)
  EnsurePackage(
      api,
      workdir,
      CPYTHON_REPO_URL,
      CPYTHON_PACKAGE_PREFIX,
      install,
      tag,
      version,
  )


def PackageGit(api):
  workdir = api.path['start_dir'].join('git')
  api.file.rmtree('rmtree workdir', workdir)
  if api.platform.is_win:
    PackageGitForWindows(api, workdir)
  else:
    PackageGitForUnix(api, workdir)


def PackageGitForUnix(api, workdir):
  """Builds Git on Unix and uploads it to a CIPD server."""

  def install(target_dir):
    # cwd is source checkout

    # Note on OS X:
    # `make configure` requires autoconf in $PATH, which is not available on
    # OS X out of box.Unfortunately autoconf is not easy to make portable, so
    # we cannot package it. However, `make install` requires XCode to be
    # present on the machine, so this installation is not hermetic anyway.
    # We treat the dependency on autoconf the same way as the dependency
    # on XCode.

    # Set NO_INSTALL_HARDLINKS to avoid hard links in
    # <target_dir>/libexec/git-core/git-*
    # because CIPD does not support them. Use symlinks instead.
    with api.step.context({'env': {'NO_INSTALL_HARDLINKS': 'VAR_PRESENT'}}):
      api.step('make configure', ['make', 'configure'])
      api.step('configure', ['./configure'])
      api.step('make install', ['make', 'install', 'prefix=%s' % target_dir])

  tag = GetLatestReleaseTag(api, GIT_REPO_URL, 'v')
  version = tag.lstrip('v')
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
  api.url.fetch_to_file(
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

  # 7z.exe does not support "RunProgram" installation header, which specifies
  # the script to run after extraction. If the downloaded exe worked, it would
  # run the post-install script. Here we hard-code the name of the file to run
  # instead of extracting it from the downloaded archive because we already have
  # to know too much about it (see below), so we have to break the API boundary
  # anyway.
  with api.step.context({'cwd': package_dir}):
    api.step(
      'post-install',
      [
        'git-bash.exe',
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

  CreatePackage(api, package_name, workdir, package_dir, version)


def GetLatestGitForWindowsRelease(api):
  """Returns a tuple (version, archive_url) for the latest release.

  Raises a StepFailure if a suitable release is not found.
  """
  # API docs:
  # https://developer.github.com/v3/repos/releases/#get-the-latest-release
  latest_release = json.loads(api.url.fetch(
      'https://api.github.com/repos/git-for-windows/git/releases/latest',
      step_name='get latest release'))
  if not latest_release:  # pragma: no cover
    raise api.step.StepFailure('latest release of Git for Windows is not found')

  asset = None
  version = None
  for a in latest_release['assets']:
    m = GIT_FOR_WINDOWS_ASSET_RE.match(str(a['name']))
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
  with api.step.context({'cwd': checkout_dir}):
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
  for (platform_name, bits, platform_suffix) in platforms:
    for new_package in ('python', 'git'):
      cpython_package_name = CPYTHON_PACKAGE_PREFIX + platform_suffix
      git_package_name = GIT_PACKAGE_PREFIX + platform_suffix
      test = (
          api.test('new_%s_on_%s' % (new_package, platform_suffix)) +
          api.platform.name(platform_name) +
          api.platform.bits(bits) +
          api.override_step_data(
              'git.cipd search %s version:2.12.2.2' % git_package_name,
              api.cipd.example_search(
                  git_package_name,
                  instances=bool(new_package != 'git')))
      )
      if platform_name != 'win':
        test += api.step_data('git.refs', git_test_refs)
        test += api.step_data('python.refs', python_test_refs)
        test += api.override_step_data(
            'python.cipd search %s version:2.1.2' % cpython_package_name,
            api.cipd.example_search(
                cpython_package_name,
                instances=bool(new_package != 'python')))
      else:
        test += api.step_data(
            'git.get latest release',
            api.raw_io.output_text(
                json.dumps(git_for_windows_release, sort_keys=True)))
        if new_package == 'git':
          test += api.step_data('git.post-install', retcode=1)
      yield test
