# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from . import util

from recipe_engine import recipe_api


REPO_URL = (
    'https://chromium.googlesource.com/external/github.com/git/git')
PACKAGE_PREFIX = 'infra/git/'

# This version suffix serves to distinguish different revisions of git built
# with this recipe.
PACKAGE_VERSION_SUFFIX = '.chromium10'


# A regex for a name of the release asset to package, available at
# https://github.com/git-for-windows/git/releases
WINDOWS_ASSET_RES = {
  32: re.compile(r'^PortableGit-(\d+(\.\d+)*)-32-bit\.7z\.exe$'),
  64: re.compile(r'^PortableGit-(\d+(\.\d+)*)-64-bit\.7z\.exe$'),
}


class GitApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self):
    workdir = self.m.path['start_dir'].join('git')
    support = self.support_prefix(workdir.join('_support'))
    self.m.file.rmtree('rmtree workdir', workdir)

    if self.m.platform.is_win:
      self._package_windows(workdir)
    else:
      self._package_unix(workdir, support)


  def _package_unix(self, workdir, support):
    """Builds Git on Unix and uploads it to a CIPD server."""

    def install(target_dir, tag):
      # Apply any applicable patches.
      patches = [self.resource('git', 'patches').join(x) for x in (
          '0001-exec_cmd-self-resolution-and-relative-pathing.patch',
          '0002-Infra-specific-extensions.patch',
      )]
      self.m.git(*[
          '-c', 'user.name=third_party_packages',
          '-c', 'user.email=third_party_packages@example.com',
          'am'] + patches)

      curl = support.ensure_curl()
      zlib = support.ensure_zlib()
      libs = (curl, zlib)

      # Note on OS X:
      # `make configure` requires autoconf in $PATH, which is not available on
      # OS X out of box. Unfortunately autoconf is not easy to make portable, so
      # we cannot package it.
      autoconf = support.ensure_autoconf()
      support_bin = autoconf.prefix.join('bin')

      # cwd is source checkout
      perl_lib_path = 'share/perl'
      env_prefixes = {
          'PATH': [support_bin],
      }
      env = {
          # This causes Git's Perl module MakeMaker build to install the Git
          # Perl module at a known path (<package>/share/perl) instead of a path
          # that is derived from the build system's Perl version. This, in turn,
          # lets us reference it as a relative path later in our custom
          # "config.mak" entry (see PERL_LIB_PATH).
          'PERL_MM_OPT': ' '.join([
            'INSTALLSITELIB=$(PREFIX)/%s' % (perl_lib_path,),
          ]),
      }

      # Extra environment additions for "configure" step.
      configure_env = {}

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
        # "RUNTIME_PREFIX" is a Windows-only feature that allows Git to probe
        # for its runtime path relative to its base path.
        #
        # Our Git patch (see resources) extends this support to Linux and Mac.
        #
        # These variables configure Git to enable and use relative runtime
        # paths.
        'RUNTIME_PREFIX = YesPlease',
        'gitexecdir = libexec/git-core',
        'template_dir = share/git-core/templates',
        'sysconfdir = etc',

        # This is a custom Infra directive that can be used to instruct Git to
        # export a deployment-relative path for Perl script imports. See custom
        # patches for more details.
        'PERL_LIB_PATH = %s' % (perl_lib_path,),

        # CIPD doesn't support hardlinks, so hardlinks become copies of the
        # original file. Use symlinks instead.
        'NO_INSTALL_HARDLINKS = YesPlease',

        # We disable "GECOS" detection. This will make the default commit user
        # name potentially less pretty, but this is acceptable, since users and
        # bots should both be setting that value.
        'NO_GECOS_IN_PWENT = YesPlease',
      ]

      if self.m.platform.is_linux:
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
        configure_env['LIBS'] = extra_libs
        custom_make_entries += [
            'EXTLIBS = %s' % (extra_libs,),
        ]
      elif self.m.platform.is_mac:
        configure_env['MACOSX_DEPLOYMENT_TARGET'] = '10.6'
        support.update_mac_autoconf(configure_env)

        # Linking "libcurl" using "--with-darwinssl" requires that we include
        # the Foundation and Security frameworks.
        ldflags += ['-framework', 'Foundation', '-framework', 'Security']

        # We have to force our static libraries into linking to prevent it from
        # linking dynamic or, worse, not seeing them at all.
        ldflags += zlib.full_static + curl.full_static

      configure_env['CPPFLAGS'] = ' '.join(cppflags)
      configure_env['CFLAGS'] = ' '.join(cflags)
      configure_env['LDFLAGS'] = ' '.join(ldflags)

      # Write our custom make entries. The "config.mak" file gets loaded AFTER
      # all the default, automatic (configure), and uname (system) entries get
      # processed, so these are final overrides.
      self.m.file.write_text(
          'Makefile specialization',
          self.m.context.cwd.join('config.mak'),
          '\n'.join(custom_make_entries + []))

      # Write the "version" file into "checkout". This is used by the
      # "GIT-VERSION-GEN" script to pull the Git version. We name ours after
      # the Git tag that we pulled and our Chromium-specific suffix, e.g.:
      # v2.12.2.chromium4
      self.m.file.write_text(
          'Version file',
          self.m.context.cwd.join('version'),
          '%s%s' % (tag, PACKAGE_VERSION_SUFFIX))

      with self.m.context(env_prefixes=env_prefixes, env=env):
        self.m.step('make configure', ['make', 'configure'])

        with self.m.context(env=configure_env):
          self.m.step('configure', [
            './configure',
            '--prefix', target_dir,
            ])

        self.m.step('make install', ['make', 'install'])

    tag = self.m.properties.get('git_release_tag')
    if not tag:
      tag = self.get_latest_release_tag(REPO_URL, 'v')
    version = tag.lstrip('v') + PACKAGE_VERSION_SUFFIX
    self.ensure_package(
        workdir,
        REPO_URL,
        PACKAGE_PREFIX,
        install,
        tag,
        version,

        # We must install via "copy", as Git copies template files verbatim, and
        # if they are symlinks, then these symlinks will be used as templates,
        # which is both incorrect and invalid.
        'copy',
    )


  def _package_windows(self, workdir):
    """Repackages Git for Windows to CIPD."""
    # Get the latest release.
    version, archive_url = self._get_latest_windows_release()

    # Search for an existing CIPD package.
    package_name = PACKAGE_PREFIX + self.m.cipd.platform_suffix()
    if self.does_package_exist(package_name, version):
      self.m.python.succeeding_step('Synced', 'Package is up to date.')
      return

    # Download the archive.
    self.m.file.ensure_directory('makedirs ensure workdir', workdir)
    archive_path = workdir.join('archive.sfx')
    self.m.url.get_file(
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
    self.m.cipd.ensure(seven_z_dir, {
      'infra/7z/${platform}': 'version:9.20',
    })
    package_dir = workdir.join('package')
    self.m.step(
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
    # instead of extracting it from the downloaded archive because we already
    # have to know too much about it (see below), so we have to break the API
    # boundary anyway.
    with self.m.context(cwd=package_dir):
      self.m.step(
        'post-install',
        [
          package_dir.join('git-bash.exe'),
          '--no-needs-console',
          '--hide',
          '--no-cd',
          '--command=post-install.bat',
        ],
        # We expect exit code 1. The post-script.bat tries to delete itself in
        # the end and it always causes a non-zero exit code.
        #
        # Note that the post-install.bat also ignores exit codes of the *.post
        # scripts that it runs, which is the important part.
        # This has been the case for at least 2yrs
        # https://github.com/git-for-windows/build-extra/commit/f1962c881ab18dd1ade087d2f5a7cac5b976f624
        #
        # BUG: https://github.com/git-for-windows/git/issues/1147
        ok_ret=(1,))

      # Change the package gitconfig defaults to match what chromium expects,
      # and enable various performance tweaks.
      settings = [
        ('core.autocrlf', 'false'),
        ('core.filemode', 'false'),
        ('core.preloadindex', 'true'),
        ('core.fscache', 'true'),
      ]
      # e.g. mingw32/etc/gitconfig
      unpacked_gitconfig = package_dir.join(
        'mingw%d' % self.m.platform.bits, 'etc', 'gitconfig')
      for setting, value in settings:
        self.m.step(
          'tweak %s=%s' % (setting, value),
          [
            package_dir.join('cmd', 'git.exe'),
            'config',
            '-f', unpacked_gitconfig,
            setting, value,
          ]
        )

      self.m.file.copy(
        'install etc/profile.d/python.sh',
        self.resource('git', 'profile.d.python.sh'),
        package_dir.join('etc', 'profile.d', 'python.sh'))

      self.m.file.copy(
        'install etc/profile.d/vpython.sh',
        self.resource('git', 'profile.d.vpython.sh'),
        package_dir.join('etc', 'profile.d', 'vpython.sh'))

    self.create_package(
        package_name,
        workdir,
        package_dir,
        version,
        None)

  def _get_latest_windows_release(self):
    """Returns a tuple (version, archive_url) for the latest release.

    Raises a StepFailure if a suitable release is not found.
    """
    # API docs:
    # https://developer.github.com/v3/repos/releases/#get-the-latest-release
    latest_release = self.m.url.get_json(
        'https://api.m.github.com/repos/git-for-windows/git/releases/latest',
        step_name='get latest release').output
    if not latest_release:  # pragma: no cover
      raise self.m.step.StepFailure(
          'latest release of Git for Windows is not found')

    asset = None
    version = None
    for a in latest_release['assets']:
      m = WINDOWS_ASSET_RES[self.m.platform.bits].match(str(a['name']))
      if not m:
        continue
      if asset is not None:  # pragma: no cover
        raise self.m.step.StepFailure(
            'multiple suitable git release assets: %s and %s' %
            (a['name'], asset['name']))
      asset = a
      version = m.group(1)
    if not asset:  # pragma: no cover
      raise self.m.step.StepFailure('could not find suitable asset')
    version += PACKAGE_VERSION_SUFFIX
    return version, asset['url']
