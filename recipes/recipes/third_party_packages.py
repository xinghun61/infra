# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This recipe builds and packages third party software, such as Git."""

import collections
import contextlib
import itertools
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
CPYTHON_PACKAGE_VERSION_SUFFIX = '.chromium5'

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
GIT_PACKAGE_VERSION_SUFFIX = '.chromium9'


def RunSteps(api):
  if not GetDryRun(api):
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  with api.step.defer_results():
    if IsWhitelisted(api, 'python'):
      if not api.platform.is_win:
        with api.step.nest('python'):
          PackagePythonForUnix(api)
    if IsWhitelisted(api, 'git'):
      with api.step.nest('git'):
        PackageGit(api)


_SourceBase = collections.namedtuple('_SourceBase', (
    # The Path to this Source's installation PREFIX.
    'prefix',
    # List of library names (e.g., "z", "curl") that this Source exports.
    'libs',
    # List of other Source entries that this Source depends on.
    'deps',
    # List of other shared libraries that this library requires when dynamically
    # linking.
    'shared_deps',
))


class SupportPrefix(object):
  """Provides a shared compilation and external library support context.

  Using SupportPrefix allows for coordination between packages (Git, Python)
  and inter-package dependencies (curl -> libz) to ensure that any given
  support library or function is built consistently and on-demand (at most once)
  for any given run.
  """

  class Source(_SourceBase):

    def _expand(self):
      exp = [self]
      for dep in self.deps:
        exp += dep._expand()
      return exp

    @property
    def cppflags(self):
      return ['-I%s/include' % (s.prefix,) for s in self._expand()]

    @property
    def ldflags(self):
      return ['-L%s' % (s.prefix.join('lib'),) for s in self._expand()]

    @property
    def static(self):
      link = []
      for s in self._expand():
        link += ['lib%s.a' % (lib,) for lib in s.libs]
      return link

    @property
    def full_static(self):
      return [str(self.prefix.join('lib', s)) for s in self.static]

    @property
    def shared(self):
      link = []
      for s in self._expand():
        link += ['-l%s' % (lib,)
                 for lib in itertools.chain(s.libs, s.shared_deps)]
      return link


  _SOURCES = {
    'infra/third_party/source/autoconf': 'version:2.69',
    'infra/third_party/source/openssl': 'version:1.1.0e',
    'infra/third_party/source/mac_openssl_headers': 'version:0.9.8zh',
    'infra/third_party/source/readline': 'version:7.0',
    'infra/third_party/source/termcap': 'version:1.3.1',
    'infra/third_party/source/zlib': 'version:1.2.11',
    'infra/third_party/source/curl': 'version:7.54.0',
  }

  def __init__(self, base):
    self._base = base
    self._built = None

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
    sources = self._base.join('sources')
    if self._built is None:
      api.cipd.ensure(sources, self._SOURCES)
      self._built = {}
    return sources

  def _ensure_and_build_once(self, api, name, tag, build_fn):
    sources = self._ensure_sources(api)
    key = (name, tag)
    prefix = self._built.get(key)
    if prefix:
      return prefix

    base = '%s-%s' % (name, tag.lstrip('version:'))
    archive = sources.join('%s.tar.gz' % (base,))

    workdir = self._base.join(base)
    api.shutil.makedirs('mkdir', workdir)

    prefix = workdir.join('prefix')
    with api.step.nest(base):
      with api.context(cwd=workdir):
        api.step('extract', ['tar', '-xzf', archive])
      build = workdir.join(base) # Archive is extracted here.

      try:
        with api.context(cwd=build):
          build_fn(prefix)
      finally:
        pass
    self._built[key] = prefix
    return prefix

  def _build_openssl(self, api, tag, shell=False):
    def build_fn(prefix):
      target = {
        ('mac', 'intel', 64): 'darwin64-x86_64-cc',
        ('linux', 'intel', 32): 'linux-x86',
        ('linux', 'intel', 64): 'linux-x86_64',
      }[(api.platform.name, api.platform.arch, api.platform.bits)]

      configure_cmd = [
        './Configure',
        '--prefix=%s' % (prefix,),
        'no-shared',
        target,
      ]
      if shell:
        configure_cmd = ['bash'] + configure_cmd

      api.step('configure', configure_cmd)
      api.step('make', ['make'])

      # Install OpenSSL. Note that "install_sw" is an OpenSSL-specific
      # sub-target that only installs headers and library, saving time.
      api.step('install', ['make', 'install_sw'])

    return self.Source(
        prefix=self._ensure_and_build_once(api, 'openssl', tag, build_fn),
        libs=['ssl', 'crypto'],
        deps=[],
        shared_deps=[])

  def ensure_static_openssl(self, api):
    return self._build_openssl(api, 'version:1.1.0e')

  def ensure_mac_native_openssl(self, api):
    return self._build_openssl(api, 'version:0.9.8zh', shell=True)

  def _generic_build(self, api, name, tag, configure_args=None, libs=None,
                     deps=None, shared_deps=None):
    def build_fn(prefix):
      api.step('configure', [
        './configure',
        '--prefix=%s' % (prefix,),
      ] + (configure_args or []))
      api.step('make', ['make', 'install'])
    return self.Source(
        prefix=self._ensure_and_build_once(api, name, tag, build_fn),
        deps=deps or [],
        libs=libs or [name],
        shared_deps=shared_deps or [])

  def ensure_curl(self, api):
    zlib = self.ensure_zlib(api)

    env = {}
    configure_args = [
      '--disable-ldap',
      '--disable-shared',
      '--without-librtmp',
      '--with-zlib=%s' % (str(zlib.prefix,)),
    ]
    deps = []
    shared_deps = []
    if api.platform.is_mac:
      configure_args += ['--with-darwinssl']
    elif api.platform.is_linux:
      ssl = self.ensure_static_openssl(api)
      env['LIBS'] = ' '.join(['-ldl', '-lpthread'])
      configure_args += ['--with-ssl=%s' % (str(ssl.prefix),)]
      deps += [ssl]
      shared_deps += ['dl', 'pthread']

    with api.context(env=env):
      return self._generic_build(api, 'curl', 'version:7.54.0',
                                 configure_args=configure_args, deps=deps,
                                 shared_deps=shared_deps)

  def ensure_zlib(self, api):
    return self._generic_build(api, 'zlib', 'version:1.2.11', libs=['z'],
                               configure_args=['--static'])

  def ensure_termcap(self, api):
    return self._generic_build(api, 'termcap', 'version:1.3.1')

  def ensure_readline(self, api):
    return self._generic_build(api, 'readline', 'version:7.0')

  def ensure_autoconf(self, api):
    return self._generic_build(api, 'autoconf', 'version:2.69')


@recipe_api.composite_step
def PackagePythonForUnix(api):
  """Builds Python for Unix and uploads it to CIPD."""

  workdir = api.path['start_dir'].join('python')
  support = SupportPrefix(workdir.join('_support'))

  tag = GetLatestReleaseTag(api, CPYTHON_REPO_URL, 'v2.')
  version = tag.lstrip('v') + CPYTHON_PACKAGE_VERSION_SUFFIX
  workdir = api.path['start_dir'].join('python')
  api.file.rmtree('rmtree workdir', workdir)

  def install(target_dir, _tag):
    # Some systems (e.g., Mac OSX) don't actually offer these libraries by
    # default, or have incorrect or inconsistent library versions. We explicitly
    # install and use controlled versions of these libraries for a more
    # controlled, consistent, and (in case of OpenSSL) secure Python build.
    readline = support.ensure_readline(api)
    termcap = support.ensure_termcap(api)
    zlib = support.ensure_zlib(api)
    libs = (readline, termcap, zlib)

    cppflags = []
    ldflags = []
    for lib in libs:
      cppflags += lib.cppflags
      ldflags += lib.ldflags

    configure_env = {
      'CPPFLAGS': ' '.join(cppflags),
      'LDFLAGS':  ' '.join(ldflags),
    }
    configure_flags = [
      '--disable-shared',
      '--prefix', target_dir,
      '--enable-ipv6',
    ]

    # Edit the modules configuration to statically compile all Python modules.
    #
    # We do this by identifying the line '#*shared*' in "/Modules/Setup.dist"
    # and replacing it with '*static*'.
    setup_local_content = [
      '*static*',
      'LIBTERMCAP_PREFIX=%s' % (termcap.prefix,),
      'binascii binascii.c %s %s' % (
          ' '.join(zlib.cppflags), ' '.join(zlib.full_static)),
      'zlib zlibmodule.c %s %s' % (
          ' '.join(zlib.cppflags), ' '.join(zlib.full_static)),
      'readline readline.c %s %s' % (
          ' '.join(readline.cppflags + termcap.cppflags),
          ' '.join(readline.full_static + termcap.full_static)),
    ]

    # If True, we will augment "ssl.py" to install default system CA certs.
    probe_default_ssl_ca_certs = False

    if api.platform.is_mac:
      # On Mac, we want to link as much statically as possible. However, Mac OSX
      # comes with an OpenSSL library that has Mac keychain support built in.
      # In order to have Python's SSL use the system keychain, we must link
      # against the native system OpenSSL libraries!
      #
      # (Note on Linux, the certificate authority is stored as a file, which we
      # can just point Python to; consequently, we compile OpenSSL statically).
      #
      # In order to link against the system OpenSSL dynamic library, we need
      # headers representing that library version. OSX doesn't come with those,
      # so we build and install an equivalent OpenSSL version and include *just
      # its headers* in our SSL module build.
      support.update_mac_autoconf(configure_env)

      configure_flags += [
          # Mac Python installations use 2-byte Unicode.
          '--enable-unicode=ucs2',

          # Flags gathered from stock Python installation.
          '--with-threads',
          '--enable-toolbox-glue',
      ]

      # On Mac, we want to link against the system OpenSSL libraries.
      #
      # Mac uses "-syslibroot", which takes ownership of library paths that
      # begin with paths matching those in the system library root, which
      # includes "/usr/lib". In order to circumvent this, we will create a
      # symlink to "/usr" called ".../systemusr", then reference it as
      # ".../systemusr/lib".
      system_usr = workdir.join('systemusr')
      api.step('symlink usr', ['ln', '-s', '/usr', system_usr])

      #
      # Note that we link against our support OpenSSL prefix headers, since the
      # system may not have them installed.
      ssl = support.ensure_mac_native_openssl(api)
      ssl_cppflags = ' '.join(ssl.cppflags)
      ssl_shared = ' '.join(ssl.shared)
      setup_local_content += [
        'SYSTEM_USR_LIB=%s/lib' % (str(system_usr),),
        '_hashlib _hashopenssl.c %s -L$(SYSTEM_USR_LIB) %s' % (
          ssl_cppflags, ssl_shared),
        '_ssl _ssl.c -DUSE_SSL %s -L$(SYSTEM_USR_LIB) %s' % (
          ssl_cppflags, ssl_shared),
      ]
    elif api.platform.is_linux:
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

        '--with-fpectl',
        '--with-dbmliborder=bdb:gdbm',
      ]

      # On Linux, we will statically compile OpenSSL into the binary, since we
      # want to be generally system/library agnostic.
      ssl = support.ensure_static_openssl(api)
      probe_default_ssl_ca_certs = True
      ssl_cppflags = ' '.join(ssl.cppflags)
      ssl_static = ' '.join(ssl.full_static)
      setup_local_content += [
        '_hashlib _hashopenssl.c %s %s' % (ssl_cppflags, ssl_static),
        '_ssl _ssl.c -DUSE_SSL %s %s' % (ssl_cppflags, ssl_static),
      ]

    setup_local = api.context.cwd.join('Modules', 'Setup.local')
    api.shutil.write(
        'Configure static modules',
        setup_local,
        '\n'.join(setup_local_content + ['']),
    )
    api.step.active_result.presentation.logs['Setup.local'] = (
        setup_local_content)

    # cwd is source checkout
    with api.context(env=configure_env):
      api.step('configure', ['./configure'] + configure_flags)

    # Build Python.
    api.step('make', ['make', 'install'])

    # Augment the Python installation.
    python_libdir = target_dir.join('lib', 'python2.7')
    api.shutil.copy(
        'install usercustomize.py',
        api.resource('python_usercustomize.py'),
        python_libdir.join('usercustomize.py'))

    if probe_default_ssl_ca_certs:
      with api.step.nest('provision SSL'):
        # Read / augment / write the "ssl.py" module to implement custom SSL
        # certificate loading logic.
        #
        # We do this here instead of "usercustomize.py" because the latter isn't
        # propagated when a VirtualEnv is cut.
        ssl_py = python_libdir.join('ssl.py')
        ssl_py_content = api.shutil.read(
            'read ssl.py',
            ssl_py)
        ssl_py_content += '\n' + api.shutil.read(
            'read ssl.py addendum',
            api.resource('python_ssl_suffix.py'),
        )
        api.shutil.write(
            'write ssl.py',
            ssl_py,
            ssl_py_content)

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
        None,
    )


@recipe_api.composite_step
def PackageGit(api):
  workdir = api.path['start_dir'].join('git')
  support = SupportPrefix(workdir.join('_support'))
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
    api.git(
        '-c', 'user.name=third_party_packages',
        '-c', 'user.email=third_party_packages@example.com',
        'am', patch)

    curl = support.ensure_curl(api)
    zlib = support.ensure_zlib(api)
    libs = (curl, zlib)

    # Note on OS X:
    # `make configure` requires autoconf in $PATH, which is not available on
    # OS X out of box. Unfortunately autoconf is not easy to make portable, so
    # we cannot package it.
    autoconf = support.ensure_autoconf(api)
    support_bin = autoconf.prefix.join('bin')

    # cwd is source checkout
    env = {
        'PATH': api.path.pathsep.join([str(support_bin), '%(PATH)s']),
    }

    cppflags = []
    ldflags = [
        '-flto',
    ]
    for lib in libs:
      cppflags += lib.cppflags

    cflags = [
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
      extra_libs = []
      for lib in libs:
        extra_libs += lib.shared
      extra_libs = ' '.join(extra_libs)

      for lib in libs:
        ldflags += lib.ldflags

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
      ldflags += zlib.full_static + curl.full_static

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

      # We must install via "copy", as Git copies template files verbatim, and
      # if they are symlinks, then these symlinks will be used as templates,
      # which is both incorrect and invalid.
      'copy',
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
  api.shutil.makedirs('ensure workdir', workdir)
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

  CreatePackage(api, package_name, workdir, package_dir, version, None)


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
    api, workdir, repo_url, package_name_prefix, install, tag, version,
    cipd_install_mode):
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

  CreatePackage(api, package_name, workdir, package_dir, version,
                cipd_install_mode)


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


def CreatePackage(api, name, workdir, root, version, install_mode):
  package_file = workdir.join('package.cipd')
  api.cipd.build(root, package_file, name, install_mode=install_mode)
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
