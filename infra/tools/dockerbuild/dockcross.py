# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import contextlib
import itertools
import os
import shutil
import stat
import string
import sys
import tempfile

from . import source
from . import util


class DockerImage(collections.namedtuple('DockerImage', (
    'name', 'tag',
    ))):

  INTERNAL_DOCKER_REGISTRY = 'gcr.io/chromium-container-registry'

  @property
  def public_id(self):
    return '%s:%s' % (self.name, self.tag)

  @property
  def internal_id(self):
    return '%s/%s:%s' % (self.INTERNAL_DOCKER_REGISTRY, self.name, self.tag)


def _docker_image_exists(system, identifier):
  rc, _, = system.docker(['inspect', identifier])
  return rc == 0


class Builder(object):

  # Tag used for pushed Docker images.
  DOCKER_IMAGE_TAG = 'v1.4.0'

  # The Docker repository to use.
  DOCKER_REPOSITORY = 'https://gcr.io'

  # The upstream tag to use when building.
  UPSTREAM_TAG = 'latest'

  # _Template contains the template parameters used in the "Dockerfile.template"
  # resource.
  _Template = collections.namedtuple('_Template', (
      'image_id', 'dockcross_base', 'resources_relpath',
      'cross_prefix', 'cross_python_prefix',
      'python27_relpath', 'python27_unicode',
      'perl5_relpath',
      'get_pip_relpath',
      'libffi_relpath', 'libffi_lib_dir',
      'cffi_relpath',
      'zlib_relpath',
      'ncurses_relpath',
      'boost_relpath',
      'mysql_relpath',
  ))


  def __init__(self, system):
    self._system = system

  @staticmethod
  def _gen_dockerfile(template):
    with open(util.resource_path('Dockerfile.template'), 'r') as fd:
      dockerfile = string.Template(fd.read())
    return dockerfile.safe_substitute(template._asdict())

  @classmethod
  def _docker_base_image(cls, plat):
    assert plat.dockcross_base_image
    return DockerImage(plat.dockcross_base_image, cls.UPSTREAM_TAG)

  def _generic_template(self, dx, root):
    """Unpack our sources in the expected Docker system layout. Populate our
    Docker template with the result.

    Since all of our Dockerfiles use the same build enviornment, we only need
    to do this once per bulk build.
    """
    repo = self._system.repo
    base_image = self._docker_base_image(dx.platform)

    # Symlink in our resources directory.
    resources = os.path.join(root, 'resources')
    shutil.copytree(util.RESOURCES_DIR, resources)

    # Install the sources that we use.
    src_dir = util.ensure_directory(root, 'sources')

    # Returns the path of "p" relative to the working root.
    def rp(p):
      return os.path.relpath(p, root)

    def ensure_src(src_name):
      """Ensures the named source from SOURCES.

      Archives are explicitly not unpacked, since they are baked into the
      resulting image and we want to minimize image size.

      Returns: (relpath, name)
        relpath (str): The path of the source, relative to the container root.
        name (str): The basename of the source (e.g., "/foo/bar" => "bar").
      """
      src = repo.ensure(SOURCES[src_name], src_dir, unpack=False)
      return rp(src)

    python_relpath = ensure_src('python')
    perl_relpath = ensure_src('perl')
    libffi_relpath = ensure_src('libffi')
    cffi_relpath = ensure_src('cffi')
    zlib_relpath = ensure_src('zlib')
    mysql_relpath = ensure_src('mysql')
    boost_relpath = ensure_src('boost')
    ncurses_relpath = ensure_src('ncurses')
    get_pip_relpath = ensure_src('get-pip')

    ucs4 = not dx.platform.wheel_abi or dx.platform.wheel_abi.endswith('mu')

    # ManyLinux base images come with multiple Pythons installed. Choose which
    # one to use, if configured.
    cross_prefix = '/usr/cross'
    if dx.platform.manylinux_name:
      cross_python_prefix = '/opt/python/%s' % (dx.platform.manylinux_name,)
    else:
      # Use the cross-compile Python that we built.
      cross_python_prefix = cross_prefix

    return self._Template(
        image_id=dx.identifier,
        dockcross_base=base_image.internal_id,
        resources_relpath=rp(resources),
        cross_prefix=cross_prefix,
        cross_python_prefix=cross_python_prefix,
        python27_relpath=python_relpath,
        python27_unicode='ucs4' if ucs4 else 'ucs2',
        perl5_relpath=perl_relpath,
        get_pip_relpath=get_pip_relpath,
        libffi_relpath=libffi_relpath,
        libffi_lib_dir='libffi-%s' % (SOURCES['libffi'].version,),
        cffi_relpath=cffi_relpath,
        zlib_relpath=zlib_relpath,
        ncurses_relpath=ncurses_relpath,
        boost_relpath=boost_relpath,
        mysql_relpath=mysql_relpath,
    )

  def mirror_base_image(self, plat, upload=False):
    docker_image = self._docker_base_image(plat)
    util.LOGGER.info('Mirroring base image [%s] => [%s]',
                     docker_image.public_id, docker_image.internal_id)

    self._pull_image(docker_image.public_id)
    self._tag_for_internal(docker_image)

    if upload:
      self._push_image(docker_image.internal_id)

  def _ensure_builder_image(self, plat, rebuild, upload):
    """Ensures that the builder image for the specified platform is installed.

    Returns: (dx, regenerated)
      dx (Image): The Image for the specified platform.
      regenerated (bool): True if the image was locally regenerated, False if it
          already existed locally.
    """

    # Build our image definition.
    dx = Image(
        system=self._system,
        platform=plat,
        bin=os.path.join(self._system.bin_dir,
                         'dockcross-%s' % (plat.name,)),
        docker_image=DockerImage(
          name='infra-dockerbuild/%s' % (plat.name,),
          tag=self.DOCKER_IMAGE_TAG,
        ),
    )

    if not rebuild:
      # If the image already exists locally, nothing else needs to be done.
      if dx.exists():
        return dx, False

      # The image doesn't exist locally, but it might exist remotely. See if we
      # can pull it.
      try:
        self._pull_image(dx.identifier)
        return dx, True
      except self._system.SubcommandError:
        util.LOGGER.debug('Could not pull image from internal mirror: [%s]',
                          dx.identifier)

    # Either we're forcing a rebuild, or the image doesn't exist locally.
    #
    # First, confirm that our base image exists locally. If not, mirror it.
    base_image = self._docker_base_image(plat)
    if not _docker_image_exists(self._system, base_image.internal_id):
      self.mirror_base_image(plat)

    # In order to build our image, we need to stage a Docker environment with
    # all of its prerequisites.
    with self._system.temp_subdir(dx.platform.name) as tdir:
      # Populate our Dockerfile template and generate our Dockerfile.
      #
      # This will also unpack prerequisites into the Docker root.
      dt = self._generic_template(dx, tdir)
      dockerfile = os.path.join(tdir, 'Dockerfile.%s' % (plat.name,))
      with open(dockerfile, 'w') as fd:
        fd.write(self._gen_dockerfile(dt))

      # Build the Docker image.
      self._system.docker([
        'build',
        '-t', dx.identifier,
        '-f', dockerfile,
        tdir,
      ], retcodes=[0])

    if upload:
      util.LOGGER.info('Uploading generated image [%s]', dx.identifier)
      self._push_image(dx.identifier)

    return dx, True

  def build(self, plat, rebuild=False, upload=False):
    if not plat.dockcross_base_image:
      return None

    # Ensure that our builder's base image exists locally.
    dx, regenerated = self._ensure_builder_image(plat, rebuild, upload)

    # If the image was regenerated, run it to generate the "dockcross" entry
    # point script.
    if regenerated or not os.path.exists(dx.bin):
      with open(dx.bin, 'w') as fd:
        self._system.docker([
            'run',
            '--rm',
            dx.identifier,
        ], stdout=fd)

        # Make the generated script executable.
        st = os.stat(dx.bin)
        os.chmod(dx.bin, st.st_mode | stat.S_IEXEC)

    return dx

  def _pull_image(self, identifier):
    self._system.docker([
      'pull',
      identifier,
    ], retcodes=[0])

  def _tag_for_internal(self, docker_image):
    self._system.docker([
      'tag',
      docker_image.public_id,
      docker_image.internal_id,
    ], retcodes=[0])

  def _push_image(self, identifier):
    self._system.docker([
      'push',
      identifier,
    ], retcodes=[0])


class Image(collections.namedtuple('_Image', (
    'system', # The toolchain instance.
    'platform', # The platform that this image represents.
    'bin', # Path to the "dockcross" wrapper script.
    'docker_image', # The builder's Docker iamge.
    ))):

  def exists(self):
    if not self.docker_image:
      # Native platform.
      return True
    return _docker_image_exists(self.system, self.identifier)

  @property
  def identifier(self):
    return self.docker_image.internal_id

  def run(self, work_dir, cmd, cwd=None, **kwargs):
    assert len(cmd) >= 1, len(cmd)
    cmd = list(cmd)

    # Replace (system) paths that include the work directory with (dockcross)
    # paths within the work directory.
    args = []
    if self.docker_image:
      # Have to handle envvars specially
      env = kwargs.pop('env', None) or {}

      # Build arguments to run within "dockcross" image.
      for i, arg in enumerate(cmd):
        if arg.startswith(work_dir):
          cmd[i] = self.workrel(work_dir, arg)
          continue

        # ...=/path/to/thing
        parts = arg.split('=', 1)
        if len(parts) == 2:
          if parts[1].startswith(work_dir):
            parts[1] = self.workrel(work_dir, parts[1])
            cmd[i] = '='.join(parts)
            continue

      # Dockcross execution
      run_args = []
      if cwd:
        # Change working directory that the image uses.
        run_args.append('-w=%s' % (self.workrel(work_dir, cwd),))

      for k, v in env.iteritems():
        v = v.replace(work_dir, '/work/')
        assert ' ' not in v, 'BUG: spaces in envvars not supported correctly'
        run_args.extend(['-e', '%s=%s' % (k, v)])

      # Run the process within the working directory.
      cwd = work_dir

      args += [self.bin]
      if run_args:
        args += ['-a', ' '.join(run_args)]

      args.append('/start.sh')

    else:
      # Build arguments to run natively.
      if cmd[0] == 'python':
        # Use system-native Python interpreter if requested.
        cmd[0] = self.system.native_python

    args += cmd
    return self.system.run(args, cwd=cwd, **kwargs)

  def check_run(self, work_dir, cmd, **kwargs):
    kwargs.setdefault('retcodes', [0])
    return self.run(work_dir, cmd, **kwargs)

  def workrel(self, work_dir, *path):
    path = os.path.relpath(os.path.join(*path), work_dir).split(os.sep)
    if self.docker_image:
      # Non-native, using "dockcross" work directory.
      work_dir = '/work'

    full_path = [work_dir] + list(path)
    return os.path.join(*full_path)


def NativeImage(system, plat):
  return Image(
      system=system,
      platform=plat,
      bin=None,
      docker_image=None)


# Sources used for Builder Docker image construction.
SOURCES = {
  'python': source.remote_archive(
    name='python',
    version='2.7.13',
    url='https://www.python.org/ftp/python/2.7.13/Python-2.7.13.tgz',
  ),

  'perl': source.remote_archive(
    name='perl',
    version='5.24.1',
    url='http://www.cpan.org/src/5.0/perl-5.24.1.tar.gz',
  ),

  'get-pip': source.remote_file(
    name='get-pip',
    version='1',
    url='https://bootstrap.pypa.io/get-pip.py',
  ),

  'zlib': source.remote_file(
    name='zlib',
    version='1.2.11',
    url='https://downloads.sourceforge.net/project/libpng/zlib/1.2.11/'
        'zlib-1.2.11.tar.gz',
  ),

  'libffi': source.remote_archive(
    name='libffi',
    version='3.2.1',
    url='ftp://sourceware.org/pub/libffi/libffi-3.2.1.tar.gz',
  ),

  'cffi': source.pypi_sdist('cffi', '1.10.0'),

  'mysql': source.remote_archive(
    name='mysql',
    version='5.7.21',
    url='https://dev.mysql.com/get/Downloads/MySQL-5.7/mysql-5.7.21.tar.gz',
  ),

  'boost': source.remote_archive(
    name='boost',
    version='1.59.0',
    # pylint: disable=line-too-long
    url='https://downloads.sourceforge.net/project/boost/boost/1.59.0/boost_1_59_0.tar.bz2',
  ),

  'ncurses': source.remote_archive(
    name='ncurses',
    version='6.1',
    url='http://ftp.gnu.org/pub/gnu/ncurses/ncurses-6.1.tar.gz',
  ),
}
