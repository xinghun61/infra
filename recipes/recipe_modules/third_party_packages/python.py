# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools

from . import util

from recipe_engine import recipe_api

REPO_URL = (
    'https://chromium.googlesource.com/external/github.com/python/cpython')
PACKAGE_PREFIX = 'infra/python/cpython/'

# This version suffix serves to distinguish different revisions of Python built
# with this recipe.
PACKAGE_VERSION_SUFFIX = '.chromium13'

class PythonApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self):
    if self.m.platform.is_win:
      # We don't currently package Python for Windows.
      return
    self._package_unix()

  def _package_unix(self):
    """Builds Python for Unix and uploads it to CIPD."""

    workdir = self.m.path['start_dir'].join('python')
    support = self.support_prefix(
        workdir.join('_support'))

    tag = self.get_latest_release_tag(REPO_URL, 'v2.')
    version = tag.lstrip('v') + PACKAGE_VERSION_SUFFIX

    # Determine our Python interpreter version. It will use PEP440's "local
    # version identifier" to specify a local Python version based on our
    # PACKAGE_VERSION_SUFFIX.
    py_version = '%s+%s' % (
        tag.lstrip('v'),
        PACKAGE_VERSION_SUFFIX.lstrip('.'))

    workdir = self.m.path['start_dir'].join('python')
    self.m.file.rmtree('rmtree workdir', workdir)

    def install(target_dir, _tag):
      # Apply any applicable patches.
      patches = [self.resource('python', 'patches').join(x) for x in (
          '0001-Update-Python-to-build-static-modules.patch',
          '0002-Enable-manual-version-specification.patch',
      )]
      self.m.git(*[
          '-c', 'user.name=third_party_packages',
          '-c', 'user.email=third_party_packages@example.com',
          'am'] + patches,
          name='git apply patches')

      # Some systems (e.g., Mac OSX) don't actually offer these libraries by
      # default, or have incorrect or inconsistent library versions. We
      # explicitly install and use controlled versions of these libraries for a
      # more controlled, consistent, and (in case of OpenSSL) secure Python
      # build.
      bzip2 = support.ensure_bzip2()
      readline = support.ensure_readline() # Pulls in "ncurses"
      zlib = support.ensure_zlib()
      sqlite = support.ensure_sqlite()
      libs = [bzip2, readline, sqlite, zlib]

      # On Linux, we need to explicitly build libnsl; on other platforms, it
      # is part of "libc".
      if self.m.platform.is_linux:
        nsl = support.ensure_nsl()
        libs.append(nsl)

      cppflags = []
      ldflags = []

      if self.m.platform.is_mac:
        # Instruct Mac to prefer ".a" files in earlier library search paths
        # rather than search all of the paths for a ".dylib" and then, failing
        # that, do a second sweep for ".a".
        ldflags.append('-Wl,-search_paths_first')

      for lib in libs:
        cppflags += lib.cppflags
        ldflags += lib.ldflags

      configure_env = {}
      configure_flags = [
        '--disable-shared',
        '--without-system-ffi',
        '--enable-ipv6',
        '--enable-py-version-override=%s' % (py_version,),
      ]
      bootstrap_configure_env = configure_env.copy()

      # Edit the modules configuration to statically compile all Python modules.
      _combine = lambda v: list(itertools.chain(*v))
      setup_local_attach = _combine(l.full_static for l in libs)
      setup_local_skip = [
          # This module is broken, and seems to reference a non-existent symbol
          # at compile time.
          '_testcapi',
      ]

      # If True, we will augment "ssl.py" to install default system CA certs.
      probe_default_ssl_ca_certs = False

      strip_flags = None
      python_bin_name = 'python'
      if self.m.platform.is_mac:
        # On Mac, the Python binary name is "python.exe". This is probably
        # because standard Mac filesystems are case insensitive and there is
        # already a "Python" directory in the checkout root.
        python_bin_name = 'python.exe'

        # On Mac, we want to link as much statically as possible. However, Mac
        # OSX comes with an OpenSSL library that has Mac keychain support built
        # in. In order to have Python's SSL use the system keychain, we must
        # link against the native system OpenSSL libraries!
        #
        # (Note on Linux, the certificate authority is stored as a file, which
        # we can just point Python to; consequently, we compile OpenSSL
        # statically).
        #
        # In order to link against the system OpenSSL dynamic library, we need
        # headers representing that library version. OSX doesn't come with
        # those, so we build and install an equivalent OpenSSL version and
        # include *just its headers* in our SSL module build.
        support.update_mac_autoconf(bootstrap_configure_env)
        support.update_mac_autoconf(configure_env)

        # Specialize configuration.
        configure_flags += [
            # Mac Python installations use 2-byte Unicode.
            '--enable-unicode=ucs2',

            # Flags gathered from stock Python installation.
            '--with-threads',
            '--enable-toolbox-glue',
        ]

        # Specialize static modules.
        setup_local_skip += [
          # Our builder system is missing X11 headers, so this module does not
          # build.
          '_tkinter',
        ]

        # On Mac, we want to link against the system OpenSSL libraries.
        #
        # Mac uses "-syslibroot", which takes ownership of library paths that
        # begin with paths matching those in the system library root, which
        # includes "/usr/lib". In order to circumvent this, we will create a
        # symlink to "/usr" called ".../systemusr", then reference it as
        # ".../systemusr/lib".
        system_usr = workdir.join('systemusr')
        self.m.step('symlink usr', ['ln', '-s', '/usr', system_usr])

        # Note that we link against our support OpenSSL prefix headers, since
        # the system may not have them installed.
        ssl = support.ensure_mac_native_openssl()
        cppflags += ssl.cppflags
        ldflags += ['-L%s/lib' % (system_usr,)]

        ssl_shared = ' '.join(ssl.shared)
        setup_local_attach += [
            '_hashlib::%s' % (ssl_shared),
            '_ssl::%s' % (ssl_shared),
        ]
      elif self.m.platform.is_linux:
        # On Linux, "-s" is an aggressive strip.
        #
        # TODO: Stripping is disabled for now, since it interferes with
        # debugging to save a few megabytes. When the Python bundle is stable,
        # we can re-enable stripping as an optimization.
        #
        # strip_flags = ['--strip-all']
        strip_flags = None

        configure_flags += [
          # Linux Python (Ubuntu) installations use 4-byte Unicode.
          '--enable-unicode=ucs4',

          '--with-fpectl',
          '--with-dbmliborder=bdb:gdbm',

          # NOTE: This can break building on Mac builder, causing it to freeze
          # during execution.
          #
          # Maybe look into this if we have time later.
          '--enable-optimizations',
        ]

        # The "crypt" module needs to link against glibc's "crypt" function.
        #
        # TODO: Maybe consider implementing a static version using OpenSSL and
        # linking that in instead?
        setup_local_attach.append('crypt::-lcrypt')

        # On Linux, we will statically compile OpenSSL into the binary, since we
        # want to be generally system/library agnostic.
        ssl = support.ensure_openssl()
        probe_default_ssl_ca_certs = True

        cppflags += ssl.cppflags
        ldflags += ssl.ldflags
        setup_local_attach += ssl.full_static

        # On Linux, we need to manually configure the embedded 'libffi' package
        # so the '_ctypes' module can link against it.
        #
        # This mirrors the non-Darwin 'libffi' path in the '_ctypes' code in
        # '//setup.py'.
        with self.m.step.nest('libffi'):
          libffi_dir = workdir.join('tpp_libffi')
          self.m.file.ensure_directory('makedirs libffi', libffi_dir)

          python_dir = self.m.context.cwd
          with self.m.context(cwd=libffi_dir):
            self.m.step(
                'configure',
                [python_dir.join('Modules', '_ctypes', 'libffi', 'configure')],
            )
            cppflags += [
                '-I%s' % (libffi_dir,),
                '-I%s' % (libffi_dir.join('include'),),
            ]

        # On Linux, we need to ensure that most symbols from our static-embedded
        # libraries (notably OpenSSL) don't get exported. If they do, they can
        # conflict with the same libraries from wheels or other dynamically
        # linked sources.
        #
        # This set of commands was determined by trial, see:
        # - crbug.com/763792
        ldflags += [
            # Tell symbols from imported static libraries to be marked as LOCAL.
            # This seems to not cover all symbols, but it gets most of them.
            '-Wl,--exclude-libs,ALL',

            # Use this to get any remaining problematic symbols.
            '-Wl,--version-script=%s' % (
              self.resource('python', 'gnu_version_script.txt'),),
        ]

      configure_env['CPPFLAGS'] = ' '.join(cppflags)
      configure_env['LDFLAGS'] = ' '.join(ldflags)

      # Build and install GNU "sed".
      #
      # This is probably not needed on Linux, but is definitely needed on Mac,
      # where the local "sed" is not GNU-compliant - notably, it cannot buffer
      # append commands longer than 2048, which our "Setup.local" augmentation
      # definitely produces.
      gnu_sed = support.ensure_gnu_sed()

      autoconf = support.ensure_autoconf()
      with self.m.context(env_prefixes={
          'PATH': [gnu_sed.bin_dir, autoconf.bin_dir],
      }):
        # Generate our configure script.
        self.m.step('generate configure', ['autoconf'])

        # Create our 'pybuilddir.txt' and bootstrap interpreter.
        #
        # The "platform" target just builds the bootstrap interpreter without
        # any modules. Unfortunately, our "setup.py" script requires several
        # modules (especially on OSX), so we build the full set of modules
        # too. The minimal target that accomplishes this is "sharedmods".
        #
        # We don't care at all about our production overrides, so we don't
        # supply any configuration parameters. We just need a package-compatible
        # interpreter. Indeed, since our "configure_env" is tailored to the
        # static build, issues have been observed performing non-static builds
        # with in including hanging compile commands.
        #
        # We build this in a separate, temporary directory so we don't get any
        # cross-talk with the production Python checkout.
        checkout_dir = self.m.context.cwd
        bootstrap_dir = workdir.join('tpp_python_bootstrap')
        self.m.file.ensure_directory('makedirs bootstrap', bootstrap_dir)
        with self.m.context(cwd=bootstrap_dir, env=bootstrap_configure_env):
          self.m.step(
              'configure bootstrap',
              [
                checkout_dir.join('configure'),
                '--prefix', bootstrap_dir.join('.prefix'),
              ] + configure_flags)

          self.m.step('make bootstrap', ['make', 'sharedmods'])

        # Configure our production Python build with our static configuration
        # environment and generate our basic platform.
        #
        # We're going to hook our bootstrap interpreter up to this platform
        # and use it to generate our static module list.
        with self.m.context(env=configure_env):
          self.m.step(
              'configure',
              [
                './configure',
                '--prefix', target_dir,
              ] + configure_flags)

          # Generate our "pybuilddir.txt" file. This also generates
          # "_sysconfigdata.py" from our current Python, which we need to
          # generate our module list, since it includes our "configure_env"'s
          # CPPFLAGS, LDFLAGS, etc.
          self.m.step('make platform', ['make', 'platform'])

        # Generate our static module list, "Modules/Setup.local". Python
        # reads this during build and projects it into its Makefile.
        #
        # The "python_mod_gen.py" script extracts a list of modules by
        # strategically invoking "setup.py", pretending that it's trying to
        # build the modules, and capturing their output. It generates a
        # "Setup.local" file.
        #
        # We need to run it with a Python interpreter that is compatible with
        # this checkout. Enter the bootstrap interpreter! However, that is
        # tailored to the bootstrap interpreter's environment ("bootstrap_dir"),
        # not the production one ("checkout_dir"). We use the
        # "python_build_bootstrap.py" script to strip that out and reorient
        # it to point to our production directory prior to invoking
        # "python_mod_gen.py".
        #
        # This is all a very elaborate (but adaptable) way to not hardcode
        # "Setup.local" for each set of platforms that we support.
        setup_local_flags = []
        setup_local_flags += [['--skip', v] for v in setup_local_skip]
        setup_local_flags += [['--attach', v] for v in setup_local_attach]
        setup_local_path = checkout_dir.join('Modules', 'Setup.local')
        self.m.step(
            'static modules',
            [
              bootstrap_dir.join(python_bin_name),
              self.resource('python', 'python_build_bootstrap.py'),
              '--root', checkout_dir,
              '--',
              self.resource('python', 'python_mod_gen.py'),
              '--output', setup_local_path,
            ] + _combine(setup_local_flags),
        )

        # Build production Python.
        self.m.step('make', ['make', 'install'])

      # Augment the Python installation.
      python_libdir = target_dir.join('lib', 'python2.7')

      if probe_default_ssl_ca_certs:
        with self.m.step.nest('provision SSL'):
          # Read / augment / write the "ssl.py" module to implement custom SSL
          # certificate loading logic.
          #
          # We do this here instead of "usercustomize.py" because the latter
          # isn't propagated when a VirtualEnv is cut.
          ssl_py = python_libdir.join('ssl.py')
          ssl_py_content = self.m.file.read_text('read ssl.py', ssl_py)
          ssl_py_content += '\n' + self.m.file.read_text(
            'read ssl.py addendum',
            self.resource('python', 'python_ssl_suffix.py'),
          )
          self.m.file.write_text('write ssl.py', ssl_py, ssl_py_content)

      # Strip the Python executable.
      #
      # NOTE: If the Python executable is ever crashing, this will remove a lot
      # of good debugging information. Comment this out to produce a package
      # with the full symbol set.
      target_python = target_dir.join('bin', 'python')
      if strip_flags is not None: # pragma: nocover
        self.m.step(
            'strip',
            ['strip'] + strip_flags + [target_python],
        )

      # Install "pip", "setuptools", and "wheel". The explicit versions are
      # those that are included in the package.
      get_pip, links, wheels = support.ensure_pip_installer()
      self.m.step(
          'pip',
          [
            target_python,
            get_pip,
            # "--prefix" is flawed, still cleans system versions.
            '--ignore-installed',
            '--no-cache-dir',
            '--no-index',
            '--find-links', links,
            '--prefix', target_dir,
          ] + ['%s==%s' % (k, v) for k, v in sorted(wheels.items())],
      )

      # Cleanup!
      for path_tuple in (
          ('lib', 'libpython2.7.a'),
          ('lib', 'python2.7', 'test'),
          ('lib', 'python2.7', 'config'),
          ):
        self.m.file.rmtree(
            'cleanup %s' % ('/'.join(path_tuple),),
            target_dir.join(*path_tuple))

      self.m.file.rmglob(
          'cleanup shared objects from lib-dynload',
          target_dir.join('lib', 'python2.7', 'lib-dynload'),
          '*.so')

    def test(package_path):
      with self.m.context(env={
        'PYTHON_TEST_CIPD_PACKAGE': package_path,
        'PYTHON_TEST_EXPECTED_VERSION': py_version,
      }):
        self.m.python(
            'test',
            self.resource('python', 'python_test.py'))

    base_env = {}
    if self.m.platform.is_mac:
      base_env['MACOSX_DEPLOYMENT_TARGET'] = '10.6'

    with self.m.context(env=base_env):
      self.ensure_package(
          workdir,
          REPO_URL,
          PACKAGE_PREFIX,
          install,
          tag,
          version,
          'copy',
          test_fn=test,
      )
