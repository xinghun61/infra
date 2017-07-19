# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import util

from recipe_engine import recipe_api

REPO_URL = (
    'https://chromium.googlesource.com/external/github.com/python/cpython')
PACKAGE_PREFIX = 'infra/python/cpython/'

# This version suffix serves to distinguish different revisions of Python built
# with this recipe.
PACKAGE_VERSION_SUFFIX = '.chromium8'

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
    workdir = self.m.path['start_dir'].join('python')
    self.m.file.rmtree('rmtree workdir', workdir)

    def install(target_dir, _tag):
      # Some systems (e.g., Mac OSX) don't actually offer these libraries by
      # default, or have incorrect or inconsistent library versions. We
      # explicitly install and use controlled versions of these libraries for a
      # more controlled, consistent, and (in case of OpenSSL) secure Python
      # build.
      readline = support.ensure_readline()
      termcap = support.ensure_termcap()
      zlib = support.ensure_zlib()
      sqlite = support.ensure_sqlite()
      libs = (readline, termcap, zlib, sqlite)

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

      if self.m.platform.is_mac:
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
        self.m.step('symlink usr', ['ln', '-s', '/usr', system_usr])

        # Note that we link against our support OpenSSL prefix headers, since
        # the system may not have them installed.
        ssl = support.ensure_mac_native_openssl()
        ssl_cppflags = ' '.join(ssl.cppflags)
        ssl_shared = ' '.join(ssl.shared)
        setup_local_content += [
          'SYSTEM_USR_LIB=%s/lib' % (str(system_usr),),
          '_hashlib _hashopenssl.c %s -L$(SYSTEM_USR_LIB) %s' % (
            ssl_cppflags, ssl_shared),
          '_ssl _ssl.c -DUSE_SSL %s -L$(SYSTEM_USR_LIB) %s' % (
            ssl_cppflags, ssl_shared),
        ]
      elif self.m.platform.is_linux:
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
        ssl = support.ensure_openssl()
        probe_default_ssl_ca_certs = True
        ssl_cppflags = ' '.join(ssl.cppflags)
        ssl_static = ' '.join(ssl.full_static)
        setup_local_content += [
          '_hashlib _hashopenssl.c %s %s' % (ssl_cppflags, ssl_static),
          '_ssl _ssl.c -DUSE_SSL %s %s' % (ssl_cppflags, ssl_static),
        ]

      setup_local = self.m.context.cwd.join('Modules', 'Setup.local')
      self.m.file.write_text(
          'Configure static modules',
          setup_local,
          '\n'.join(setup_local_content + ['']),
      )
      self.m.step.active_result.presentation.logs['Setup.local'] = (
          setup_local_content)

      # cwd is source checkout
      with self.m.context(env=configure_env):
        self.m.step('configure', ['./configure'] + configure_flags)

      # Build Python.
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

      # Install "pip", "setuptools", and "wheel". The explicit versions are
      # those that are included in the package.
      target_python = target_dir.join('bin', 'python')
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
          ('include',),
          ('lib', 'libpython2.7.a'),
          ('lib', 'python2.7', 'test'),
          ('lib', 'python2.7', 'config'),
          ):
        self.m.file.rmtree(
            'cleanup %s' % ('/'.join(path_tuple),),
            target_dir.join(*path_tuple))

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
      )
