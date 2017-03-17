# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions to work with Miniconda python environment.

See http://conda.pydata.org/miniconda.html
"""

from recipe_engine import recipe_api


class CondaEnv(object):
  def __init__(self, module_api, version, path):
    self._module_api = module_api
    self.version = version
    self.path = path
    self._wiped = False

  def __enter__(self, *_args):
    return self

  def __exit__(self, *_args):
    self.wipe()

  @property
  def conda_exe(self):
    """Path to 'conda' executable."""
    if self._module_api.m.platform.is_win:
      return self.path.join('Scripts', 'conda.exe')
    return self.path.join('bin', 'conda')

  def install(self, pkg):
    """Installs a conda package into the environment."""
    return self._call(['install', pkg])

  def convert_to_cipd_package(self, package_name, output_file):
    """Packages Conda environment as CIPD package.

    It also breaks it in the process (by irreversibly mutating it to be
    prefix independent, as much as possible). It is not possible to install
    new packages into the environment once it has been mutated.

    Args:
      package_name: name of the CIPD package, 'infra/conda_python/linux-amd64'.
      output_file: path to put *.cipd package to.
    """
    self._call(['clean', '--tarballs', '--index-cache', '--packages'])
    self._module_api.m.python(
        'make conda env location independent',
        self._module_api.resource('butcher_conda.py'),
        args=[self.path])
    self._module_api.m.cipd.build(
        input_dir=self.path,
        output_package=output_file,
        package_name=package_name,
        install_mode='copy')

  def wipe(self):
    """Wipes the directory with Conda installation."""
    if not self._wiped:
      self._wiped = True
      self._module_api.m.file.rmtree('removing conda', self.path)

  def _call(self, cmd):
    with self._module_api.m.step.context({'env': {'PYTHONPATH': None}}):
      return self._module_api.m.step(
          ' '.join(['conda'] + cmd),
          [self.conda_exe] + cmd + ['--yes'])


class CondaApi(recipe_api.RecipeApi):
  def install(self, version, path):
    """Downloads Miniconda installer for given version and executes it.

    Args:
      version: version of Miniconda to install, e.g. 'Miniconda2-3.18.3'.
      path: prefix to install Miniconda into.

    Returns:
      Instance of CondaEnv, that also optionally acts as context manager that
      deletes the environment on exit.
    """
    # Construct URL to installer. See https://repo.continuum.io/miniconda/.
    os = {
      'linux': 'Linux',
      'mac': 'MacOSX',
      'win': 'Windows',
    }[self.m.platform.name]
    arch = {
      32: 'x86',
      64: 'x86_64',
    }[self.m.platform.bits]
    ext = '.exe' if self.m.platform.is_win else '.sh'
    url = (
        'https://repo.continuum.io/miniconda/%s-%s-%s%s' %
        (version, os, arch, ext))

    # Fetch installer into temp directory and install Conda to 'path'.
    # We acknowledge the license agreement.
    tmp = self.m.path.mkdtemp('conda')
    installer = tmp.join(url[url.rfind('/')+1:])
    try:
      self.m.url.fetch_to_file(
          url=url,
          path=installer,
          step_name='fetch miniconda installer',
          attempts=5)
      # See http://conda.pydata.org/docs/help/silent.html
      if self.m.platform.is_win:
        install_cmd = [
          installer, '/InstallationType=JustMe', '/AddToPath=0',
          '/RegisterPython=0', '/S', '/D=' + str(path),
        ]
      else:
        install_cmd = ['/bin/bash', installer, '-b', '-p', path]
      with self.m.step.context({'env': {'PYTHONPATH': ''}}):
        self.m.step('install miniconda', install_cmd)
      return CondaEnv(self, version, path)
    finally:
      self.m.file.rmtree('remove miniconda installer', tmp)
