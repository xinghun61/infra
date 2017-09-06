# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import itertools

from . import util


class Source(collections.namedtuple('_SourceBase', (
    # The Path to this Source's installation PREFIX.
    'prefix',
    # List of library names (e.g., "z", "curl") that this Source exports.
    'libs',
    # List of other Source entries that this Source depends on.
    'deps',
    # List of other shared libraries that this library requires when dynamically
    # linking.
    'shared_deps',
    ))):

  def __new__(cls, *args, **kwargs):
    include_prefix = kwargs.pop('include_prefix', None)
    src = super(Source, cls).__new__(cls, *args, **kwargs)
    src.include_prefix = include_prefix or src.prefix
    return src

  def _expand(self):
    exp = [self]
    for dep in self.deps:
      exp += dep._expand()
    return exp

  @property
  def bin_dir(self):
    return self.prefix.join('bin')

  @property
  def include_dirs(self):
    return [d.include_prefix.join('include') for d in self._expand()]

  @property
  def cppflags(self):
    return ['-I%s' % (d,) for d in self.include_dirs]

  @property
  def lib_dirs(self):
    return [d.include_prefix.join('lib') for d in self._expand()]

  @property
  def ldflags(self):
    return ['-L%s' % (d,) for d in self.lib_dirs]

  @property
  def full_static(self):
    full = []
    for s in self._expand():
      full += [str(s.include_prefix.join('lib', 'lib%s.a' % (lib,)))
               for lib in s.libs]
    return full

  @property
  def shared(self):
    link = []
    for s in self._expand():
      link += ['-l%s' % (lib,)
               for lib in itertools.chain(s.libs, s.shared_deps)]
    return link


class SupportPrefix(util.ModuleShim):
  """Provides a shared compilation and external library support context.

  Using SupportPrefix allows for coordination between packages (Git, Python)
  and inter-package dependencies (curl -> libz) to ensure that any given
  support library or function is built consistently and on-demand (at most once)
  for any given run.
  """

  _SOURCES = {
    'infra/third_party/source/autoconf': 'version:2.69',
    'infra/third_party/source/gnu_sed': 'version:4.2.2',
    'infra/third_party/source/bzip2': 'version:1.0.6',
    'infra/third_party/source/openssl': 'version:1.1.0e',
    'infra/third_party/source/mac_openssl_headers': 'version:0.9.8zh',
    'infra/third_party/source/pcre2': 'version:10.23',
    'infra/third_party/source/readline': 'version:7.0',
    'infra/third_party/source/zlib': 'version:1.2.11',
    'infra/third_party/source/curl': 'version:7.54.0',
    'infra/third_party/source/ncurses': 'version:6.0',
    'infra/third_party/source/nsl': 'version:1.0.4',
    'infra/third_party/source/sqlite-autoconf': 'version:3.19.3',
    'infra/third_party/pip-packages': 'version:9.0.1',
  }

  # The name and versions of the universal wheels in "pip-packages" that should
  # be installed alongside "pip".
  #
  # This will be versioned with _SOURCES's "pip-packages" entry.
  _PIP_PACKAGES_WHEELS = {
    'pip': '9.0.1',
    'setuptools': '36.0.1',
    'wheel': '0.30.0a0',
  }

  def __init__(self, api, base):
    super(SupportPrefix, self).__init__(api)
    self._api = api
    self._base = base
    self._sources_installed = False
    self._built = {}

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

  def ensure_sources(self):
    sources = self._base.join('sources')
    if not self._sources_installed:
      self.m.cipd.ensure(sources, self._SOURCES)
      self._sources_installed = True
    return sources

  def _build_once(self, key, build_fn):
    result = self._built.get(key)
    if result:
      return result

    build_name = '-'.join(e for e in key if e)
    workdir = self._base.join(build_name)

    with self.m.step.nest(build_name):
      self.m.file.ensure_directory('makedirs workdir', workdir)

      with self.m.context(cwd=workdir):
        self._built[key] = build_fn()
    return self._built[key]

  def _ensure_and_build_archive(self, name, tag, build_fn, archive_name=None,
                                variant=None):
    sources = self.ensure_sources()
    archive_name = archive_name or '%s-%s.tar.gz' % (
        name, tag.lstrip('version:'))

    base = archive_name
    for ext in ('.tar.gz', '.tgz', '.zip'):
      if base.endswith(ext):
        base = base[:-len(ext)]
        break

    def build_archive():
      archive = sources.join(archive_name)
      prefix = self.m.context.cwd.join('prefix')

      self.m.python(
          'extract',
          self.resource('archive_util.py'),
          [
            archive,
            self.m.context.cwd,
          ])
      build = self.m.context.cwd.join(base) # Archive is extracted here.

      try:
        with self.m.context(cwd=build):
          build_fn(prefix)
      finally:
        pass
      return prefix

    key = (base, variant)
    return self._build_once(key, build_archive)

  def _build_openssl(self, tag, shell=False):
    def build_fn(prefix):
      target = {
        ('mac', 'intel', 64): 'darwin64-x86_64-cc',
        ('linux', 'intel', 32): 'linux-x86',
        ('linux', 'intel', 64): 'linux-x86_64',
      }[(
        self.m.platform.name,
        self.m.platform.arch,
        self.m.platform.bits)]

      configure_cmd = [
        './Configure',
        '--prefix=%s' % (prefix,),
        'no-shared',
        target,
      ]
      if shell:
        configure_cmd = ['bash'] + configure_cmd

      self.m.step('configure', configure_cmd)
      self.m.step('make', ['make'])

      # Install OpenSSL. Note that "install_sw" is an OpenSSL-specific
      # sub-target that only installs headers and library, saving time.
      self.m.step('install', ['make', 'install_sw'])

    return Source(
        prefix=self._ensure_and_build_archive('openssl', tag, build_fn),
        libs=['ssl', 'crypto'],
        deps=[],
        shared_deps=[])

  def ensure_openssl(self):
    return self._build_openssl('version:1.1.0e')

  def ensure_mac_native_openssl(self):
    return self._build_openssl('version:0.9.8zh', shell=True)

  def _generic_build(self, name, tag, archive_name=None, configure_args=None,
                     libs=None, deps=None, shared_deps=None):
    def build_fn(prefix):
      self.m.step('configure', [
        './configure',
        '--prefix=%s' % (prefix,),
      ] + (configure_args or []))
      self.m.step('make', ['make', 'install'])
    return Source(
        prefix=self._ensure_and_build_archive(
          name, tag, build_fn, archive_name=archive_name),
        deps=deps or [],
        libs=libs or [name],
        shared_deps=shared_deps or [])

  def ensure_curl(self):
    zlib = self.ensure_zlib()

    env = {}
    configure_args = [
      '--disable-ldap',
      '--disable-shared',
      '--without-librtmp',
      '--with-zlib=%s' % (str(zlib.prefix,)),
    ]
    deps = []
    shared_deps = []
    if self.m.platform.is_mac:
      configure_args += ['--with-darwinssl']
    elif self.m.platform.is_linux:
      ssl = self.ensure_openssl()
      env['LIBS'] = ' '.join(['-ldl', '-lpthread'])
      configure_args += ['--with-ssl=%s' % (str(ssl.prefix),)]
      deps += [ssl]
      shared_deps += ['dl', 'pthread']

    with self.m.context(env=env):
      return self._generic_build('curl', 'version:7.54.0',
                                 configure_args=configure_args, deps=deps,
                                 shared_deps=shared_deps)

  def ensure_pcre2(self):
    return self._generic_build(
        'pcre2',
        'version:10.23',
        libs=['pcre2-8'],
        configure_args=[
          '--enable-static',
          '--disable-shared',
        ])

  def ensure_nsl(self):
    return self._generic_build('nsl', 'version:1.0.4',
        archive_name='libnsl-1.0.4.tar.gz',
        configure_args=['--disable-shared'])

  def ensure_ncurses(self):
    return self._generic_build('ncurses', 'version:6.0',
        libs=['panel', 'ncurses'])

  def ensure_zlib(self):
    return self._generic_build('zlib', 'version:1.2.11', libs=['z'],
                               configure_args=['--static'])

  def ensure_sqlite(self):
    return self._generic_build('sqlite', 'version:3.19.3', libs=['sqlite3'],
        configure_args=[
          '--enable-static',
          '--disable-shared',
          '--with-pic',
          '--enable-fts5',
          '--enable-json1',
          '--enable-session',
        ],
        archive_name='sqlite-autoconf-3190300.tar.gz')

  def ensure_bzip2(self):
    def build_fn(prefix):
      self.m.step('make', [
        'make',
        'install',
        'PREFIX=%s' % (prefix,),
      ])
    return Source(
        prefix=self._ensure_and_build_archive(
          'bzip2', 'version:1.0.6', build_fn),
        deps=[],
        libs=['bz2'],
        shared_deps=[])

  def ensure_readline(self):
    ncurses = self.ensure_ncurses()
    return self._generic_build('readline', 'version:7.0',
        configure_args=[
          '--with-curses',
        ],
        deps=[ncurses])

  def ensure_autoconf(self):
    return self._generic_build('autoconf', 'version:2.69')

  def ensure_gnu_sed(self):
    return self._generic_build('gnu_sed', 'version:4.2.2',
        archive_name='sed-4.2.2.tar.gz')

  def ensure_pip_installer(self):
    """Returns information about the pip installation.

    Returns: (get_pip, links_path, wheels)
      get_pip (Path): Path to the "get-pip.py" script.
      links (Path): Path to the links directory containing all installation
          wheels.
      wheels (dict): key/value mapping of "pip" installation packages names
          and their verisons.
    """
    sources = self.ensure_sources()
    return (
        sources.join('get-pip.py'),
        sources,
        self._PIP_PACKAGES_WHEELS,
    )
