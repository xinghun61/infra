# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This recipe builds and packages third party software, such as Git."""

import contextlib
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
CPYTHON_PACKAGE_VERSION_SUFFIX = '.chromium3'

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
GIT_PACKAGE_VERSION_SUFFIX = '.chromium6'


def RunSteps(api):
  if not GetDryRun(api):
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  support = SupportPrefix(api.path['start_dir'].join('_support'))
  with api.step.defer_results():
    if IsWhitelisted(api, 'python'):
      if not api.platform.is_win:
        with api.step.nest('python'):
          PackagePythonForUnix(api, support)
    if IsWhitelisted(api, 'git'):
      with api.step.nest('git'):
        PackageGit(api, support)


class SupportPrefix(object):
  """Provides a shared compilation and external library support context.

  Using SupportPrefix allows for coordination between packages (Git, Python)
  and inter-package dependencies (curl -> libz) to ensure that any given
  support library or function is built consistently and on-demand (at most once)
  for any given run.
  """

  _SOURCES = {
    'infra/third_party/source/autoconf': 'version:2.69',
    'infra/third_party/source/openssl': 'version:1.1.0e',
    'infra/third_party/source/readline': 'version:7.0',
    'infra/third_party/source/termcap': 'version:1.3.1',
    'infra/third_party/source/zlib': 'version:1.2.11',
    'infra/third_party/source/curl': 'version:7.54.0',
    'infra/third_party/cacert': 'date:2017-01-18',
  }

  def __init__(self, base):
    self._build = base.join('build')
    self._prefix = base.join('prefix')
    self._built = None

  @property
  def prefix(self):
    return self._prefix

  @staticmethod
  def update_mac_autoconf(env):
    # Several functions are declared in OSX headers that aren't actually
    # present in its standard libraries. Autoconf will succeed at detecting
    # them, only to fail later due to a linker error. Override these autoconf
    # variables via env to prevent this.
    env.update({
        'ac_cv_func_getentropy': 'n',
        'ac_cv_func_clock_gettime': 'n',
    })

  def _ensure_sources(self, api):
    sources = self._build.join('sources')
    if self._built is None:
      api.cipd.ensure(sources, self._SOURCES)
      self._built = set()
    return sources

  @contextlib.contextmanager
  def _ensure_and_build_once(self, api, name, build_fn):
    sources = self._ensure_sources(api)
    if name in self._built:
      return

    for k, v in self._SOURCES.iteritems():
      if k.endswith('/' + name):
        base = '%s-%s' % (name, v.lstrip('version:'))
        archive = sources.join('%s.tar.gz' % (base,))
        break
    else: # pragma: no cover
      raise KeyError('Unknown package [%s]' % (name,))

    with api.step.nest(base):
      with api.context(cwd=self._build):
        api.step('extract', ['tar', '-xzf', archive])

      try:
        with api.context(cwd=self._build.join(base)):
          build_fn()
        self._built.add(name)
      finally:
        pass

  def ensure_openssl(self, api):
    def build_fn():
      target = {
        ('mac', 'intel', 64): 'darwin64-x86_64-cc',
        ('linux', 'intel', 32): 'linux-x86',
        ('linux', 'intel', 64): 'linux-x86_64',
      }[(api.platform.name, api.platform.arch, api.platform.bits)]

      api.step('configure', [
        './Configure',
        '--prefix=%s' % (self.prefix,),
        'no-shared',
        target,
      ])
      api.step('make', ['make'])

      # Install OpenSSL. Note that "install_sw" is an OpenSSL-specific
      # sub-target that only installs headers and library, saving time.
      api.step('install', ['make', 'install_sw'])
    self._ensure_and_build_once(api, 'openssl', build_fn)

  def _generic_build(self, api, name, configure_args=None):
    def build_fn():
      api.step('configure', [
        './configure',
        '--prefix=%s' % (self.prefix,),
      ] + (configure_args or []))
      api.step('make', ['make', 'install'])
    self._ensure_and_build_once(api, name, build_fn)

  def ensure_curl(self, api):
    self.ensure_zlib(api)

    env = {}
    configure_args = [
      '--disable-ldap',
      '--disable-shared',
      '--without-librtmp',
      '--with-zlib=%s' % (str(self.prefix,)),
    ]
    if api.platform.is_mac:
      configure_args += ['--with-darwinssl']
    elif api.platform.is_linux:
      self.ensure_openssl(api)
      env['LIBS'] = ' '.join(['-ldl', '-lpthread'])
      configure_args += ['--with-ssl=%s' % (str(self.prefix),)]

    with api.context(env=env):
      return self._generic_build(api, 'curl', configure_args=configure_args)

  def ensure_zlib(self, api):
    return self._generic_build(api, 'zlib', configure_args=['--static'])

  def ensure_termcap(self, api):
    return self._generic_build(api, 'termcap')

  def ensure_readline(self, api):
    return self._generic_build(api, 'readline')

  def ensure_autoconf(self, api):
    return self._generic_build(api, 'autoconf')

  def ensure_cacert(self, api):
    return self._ensure_sources(api).join('cacert.pem')


@recipe_api.composite_step
def PackagePythonForUnix(api, support):
  """Builds Python for Unix and uploads it to CIPD."""

  workdir = api.path['start_dir'].join('python')

  tag = GetLatestReleaseTag(api, CPYTHON_REPO_URL, 'v2.')
  version = tag.lstrip('v') + CPYTHON_PACKAGE_VERSION_SUFFIX
  workdir = api.path['start_dir'].join('python')
  api.file.rmtree('rmtree workdir', workdir)

  def install(target_dir, _tag):
    # Some systems (e.g., Mac OSX) don't actually offer these libraries by
    # default, or have incorrect or inconsistent library versions. We explicitly
    # install and use controlled versions of these libraries for a more
    # controlled, consistent, and (in case of OpenSSL) secure Python build.
    support.ensure_openssl(api)
    support.ensure_readline(api)
    support.ensure_termcap(api)
    support.ensure_zlib(api)

    support_lib = support.prefix.join('lib')
    support_include = support.prefix.join('include')

    cppflags = [
      '-I%s' % (support_include,),
    ]
    ldflags = [
      '-L%s' % (support_lib,),
    ]

    configure_env = {
      'CPPFLAGS': ' '.join(cppflags),
      'LDFLAGS':  ' '.join(ldflags),
    }
    configure_flags = [
      '--disable-shared',
      '--prefix', target_dir,
    ]

    if api.platform.is_mac:
      support.update_mac_autoconf(configure_env)

      # Mac Python installations use 2-byte Unicode.
      configure_flags += ['--enable-unicode=ucs2']
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

        # Linux Python (Ubuntu) installations use 4-byte Unicode.
        '--enable-unicode=ucs4',
      ]

    # Edit the modules configuration to statically compile all Python modules.
    #
    # We do this by identifying the line '#*shared*' in "/Modules/Setup.dist"
    # and replacing it with '*static*'.
    setup_local_content = [
      '*static*',
      'SP=%s' % (support.prefix,),
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
    setup_local = api.context.cwd.join('Modules', 'Setup.local')
    api.shutil.write(
        'Configure static modules',
        setup_local,
        '\n'.join(setup_local_content),
    )
    api.step.active_result.presentation.logs['Setup.local'] = (
        setup_local_content)

    # cwd is source checkout
    with api.context(env=configure_env):
      api.step('configure', ['./configure'] + configure_flags)

    # Build Python.
    api.step('make', ['make', 'install'])

    # Install "cacert.pem".
    python_libdir = target_dir.join('lib', 'python2.7')
    api.shutil.copy(
        'install cacert.pem',
        support.ensure_cacert(api),
        python_libdir.join('cacert.pem'))

    # Install "usercustomize.py".
    api.shutil.copy(
        'install usercustomize.py',
        api.resource('python_usercustomize.py'),
        python_libdir.join('usercustomize.py'))

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
def PackageGit(api, support):
  workdir = api.path['start_dir'].join('git')
  api.file.rmtree('rmtree workdir', workdir)
  if api.platform.is_win:
    PackageGitForWindows(api, workdir)
  else:
    PackageGitForUnix(api, workdir, support)


def PackageGitForUnix(api, workdir, support):
  """Builds Git on Unix and uploads it to a CIPD server."""

  def install(target_dir, _tag):
    # Apply any applicable patches.
    patch = api.resource('git_2_13_0.posix.patch')
    api.git('apply', patch)

    support.ensure_curl(api)
    support.ensure_zlib(api)

    # Note on OS X:
    # `make configure` requires autoconf in $PATH, which is not available on
    # OS X out of box. Unfortunately autoconf is not easy to make portable, so
    # we cannot package it.
    support.ensure_autoconf(api)
    support_bin = support.prefix.join('bin')

    # cwd is source checkout
    env = {
        'PATH': api.path.pathsep.join([str(support_bin), '%(PATH)s']),
    }

    support_include = support.prefix.join('include')
    support_lib = support.prefix.join('lib')

    cppflags = [
        '-I%s' % (str(support_include,)),
    ]
    cflags = [
        '-flto',
    ]
    ldflags = [
        '-L%s' % (str(support_lib,)),
        '-flto',
    ]

    # Override the autoconfig / system Makefile entries with custom ones.
    custom_make_entries = [
      # "RUNTIME_PREFIX" is a Windows-only feature that allows Git to probe for
      # its runtime path relative to its base path.
      #
      # Our Git patch (see resources) extends this support to Linux and Mac.
      #
      # These variables configure Git to enable and use relative runtime paths.
      'RUNTIME_PREFIX = YesPlease',
      'gitexecdir = libexec/git-core',
      'template_dir = share/git-core/templates',
      'sysconfdir = etc',

      # CIPD doesn't support hardlinks, so hardlinks become copies of the
      # original file. Use symlinks instead.
      'NO_INSTALL_HARDLINKS = YesPlease',

      # We disable "GECOS" detection. This will make the default commit user
      # name potentially less pretty, but this is acceptable, since users and
      # bots should both be setting that value.
      'NO_GECOS_IN_PWENT = YesPlease',
    ]

    if api.platform.is_linux:
      # Since we're supplying these libraries, we need to explicitly include
      # them in our LIBS (for "configure" probing) and our Makefile on Linux.
      #
      # Normally we'd use the LIBS environment variable for both, but that
      # doesn't make its way to the Makefile (bug?). Therefore, the most
      # direct way to do this is to find the line in Git's "Makefile" that
      # initializes EXTLIBS and add the dependent libraries to it :(
      extra_libs = ' '.join(['-l%s' % (l,) for l in (
        'ssl', 'crypto', 'z', 'pthread', 'dl',
      )])

      # autoconf and make needs these flags to properly detect the build
      # environment.
      env['LIBS'] = extra_libs
      custom_make_entries += [
          'EXTLIBS = %s' % (extra_libs,),
      ]
    elif api.platform.is_mac:
      env['MACOSX_DEPLOYMENT_TARGET'] = '10.6'
      support.update_mac_autoconf(env)

      # Linking "libcurl" using "--with-darwinssl" requires that we include
      # the Foundation and Security frameworks.
      ldflags += ['-framework', 'Foundation', '-framework', 'Security']

      # We have to force our static libraries into linking to prevent it from
      # linking dynamic or, worse, not seeing them at all.
      ldflags += [str(support.prefix.join('lib', stlib)) for stlib in (
        'libz.a', 'libcurl.a',
      )]

    env['CPPFLAGS'] = ' '.join(cppflags)
    env['CFLAGS'] = ' '.join(cflags)
    env['LDFLAGS'] = ' '.join(ldflags)

    # Write our custom make entries. The "config.mak" file gets loaded AFTER
    # all the default, automatic (configure), and uname (system) entries get
    # processed, so these are final overrides.
    api.shutil.write(
        'Makefile specialization',
        api.context.cwd.join('config.mak'),
        '\n'.join(custom_make_entries + []))

    with api.context(env=env):
      api.step('make configure', ['make', 'configure'])
      api.step('configure', [
        './configure',
        '--prefix', target_dir,
        ])

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
    install(package_dir, tag)

  CreatePackage(api, package_name, workdir, package_dir, version)


def GetDryRun(api):
  """Returns the "dry_run" property value.

  To enable dry run, set "dry_run" to either be a string, specifying a specific
  package name to build, or a true value to perform a full dry run. If missing
  or a false value, this recipe will perform a production run.
  """
  return api.properties.get('dry_run')


def IsWhitelisted(api, key):
  dry_run = GetDryRun(api)
  return (not isinstance(dry_run, basestring)) or dry_run == key


def CreatePackage(api, name, workdir, root, version):
  package_file = workdir.join('package.cipd')
  api.cipd.build(root, package_file, name)
  if not GetDryRun(api):
    api.cipd.register(name, package_file, tags={'version': version})


def DoesPackageExist(api, name, version):
  search = api.cipd.search(name, 'version:' + version)
  return bool(search.json.output['result'] and not GetDryRun(api))


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

  yield (
      api.test('dry_run') +
      api.properties(dry_run=True) +
      api.platform.name('linux') +
      api.platform.bits(64) +
      api.step_data('python.refs', python_test_refs) +
      api.step_data('git.refs', git_test_refs)
  )
