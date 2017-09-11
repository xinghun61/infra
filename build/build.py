#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script rebuilds Python & Go universes of infra.git multiverse and
invokes CIPD client to package and upload chunks of it to the CIPD repository as
individual packages.

See build/packages/*.yaml for definition of packages and README.md for more
details.
"""

import argparse
import collections
import contextlib
import copy
import glob
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile


# Root of infra.git repository.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Root of infra gclient solution.
GCLIENT_ROOT = os.path.dirname(ROOT)

# Where to upload packages to by default.
PACKAGE_REPO_SERVICE = 'https://chrome-infra-packages.appspot.com'

# True if running on Windows.
IS_WINDOWS = sys.platform == 'win32'

# .exe on Windows.
EXE_SUFFIX = '.exe' if IS_WINDOWS else ''


class BuildException(Exception):
  """Raised on errors during package build step."""


class UploadException(Exception):
  """Raised on errors during package upload step."""


class PackageDef(collections.namedtuple(
    '_PackageDef', ('path', 'pkg_def'))):
  """Represents parsed package *.yaml file."""

  @property
  def name(self):
    """Returns name of YAML file (without the directory path and extension)."""
    return os.path.splitext(os.path.basename(self.path))[0]

  @property
  def uses_python_env(self):
    """Returns True if 'uses_python_env' in the YAML file is set."""
    return bool(self.pkg_def.get('uses_python_env'))

  @property
  def go_packages(self):
    """Returns a list of Go packages that must be installed for this package."""
    return self.pkg_def.get('go_packages') or []

  @property
  def pkg_root(self):
    """Absolute path to a package root directory."""
    root = self.pkg_def['root'].replace('/', os.sep)
    if os.path.isabs(root):
      return root
    return os.path.abspath(os.path.join(os.path.dirname(self.path), root))

  def should_build(self, builder, host_vars):
    """Returns True if package should be built in the current environment.

    Takes into account 'builders' and 'supports_cross_compilation' properties of
    the package definition file.
    """
    # If '--builder' is not specified, ignore 'builders' property. Otherwise, if
    # 'builders' YAML attribute it not empty, verify --builder is listed there.
    builders = self.pkg_def.get('builders')
    if builder and builders and builder not in builders:
      return False

    # If cross-compiling, pick only packages that support cross-compilation.
    if (is_cross_compiling() and
        not self.pkg_def.get('supports_cross_compilation')):
      return False

    # Verify target platform is supported for the package if they're specified.
    supported_platforms = self.pkg_def.get('supported_platforms')
    if supported_platforms:
      target_platform = (os.environ.get('GOOS') or
                         host_vars['platform'].split('-')[0])
      return target_platform in supported_platforms

    return True

  def preprocess(self, pkg_vars):
    """Parses the definition and filters/extends it before passing to CIPD.

    This process may generate additional files that are put into the package.

    Args:
      pkg_vars: dict with variables passed to cipd as -pkg-var.

    Returns:
      (Path to filtered package definition YAML, list of generated files).
    """
    pkg_def = copy.deepcopy(self.pkg_def)
    gen_files = []

    # Generate *.bat shims when targeting Windows.
    if is_targeting_windows(pkg_vars):
      for d in pkg_def['data'][:]:
        if d.get('generate_bat_shim'):
          # Generate actual *.bat.
          bat_abs = generate_bat_shim(
              self.pkg_root, render_path(d.get('file'), pkg_vars))
          # Make it part of the package definition (use slash paths there).
          pkg_def['data'].append({
            'file': os.path.relpath(bat_abs, self.pkg_root).replace(os.sep, '/')
          })
          # Stage it for cleanup.
          gen_files.append(bat_abs)

    # Keep generated yaml in the same directory to avoid rewriting paths.
    out_path = os.path.join(
        os.path.dirname(self.path), self.name + '.processed_yaml')
    with open(out_path, 'w') as f:
      json.dump(pkg_def, f)
    return out_path, gen_files


def render_path(p, pkg_vars):
  """Renders ${...} substitutions in paths, converts them to native slash."""
  for k, v in pkg_vars.iteritems():
    assert '${' not in v  # just in case, to avoid recursive expansion
    p = p.replace('${%s}' % k, v)
  return p.replace('/', os.sep)


def generate_bat_shim(pkg_root, target_rel):
  """Writes a shim file side-by-side with target and returns abs path to it."""
  target_name = os.path.basename(target_rel)
  bat_name = os.path.splitext(target_name)[0] + '.bat'
  base_dir = os.path.dirname(os.path.join(pkg_root, target_rel))
  bat_path = os.path.join(base_dir, bat_name)
  with open(bat_path, 'w') as fd:
    fd.write('\n'.join([  # python turns \n into CRLF
    '@set CIPD_EXE_SHIM="%%~dp0%s"' % (target_name,),
    '@shift',
    '@%CIPD_EXE_SHIM% %*',
    ''
  ]))
  return bat_path


def is_cross_compiling():
  """Returns True if using GOOS or GOARCH env vars.

  We also check at the start of the script that if one of them is used, then
  the other is specified as well.
  """
  return bool(os.environ.get('GOOS')) or bool(os.environ.get('GOARCH'))


def get_env_dot_py():
  if os.environ.get('GOOS') == 'android':
    return 'mobile_env.py'
  else:
    return 'env.py'


def run_python(script, args):
  """Invokes a python script.

  Raises:
    subprocess.CalledProcessError on non zero exit code.
  """
  print 'Running %s %s' % (script, ' '.join(args))
  subprocess.check_call(
      args=['python', '-u', script] + list(args), executable=sys.executable)


def run_cipd(cipd_exe, cmd, args):
  """Invokes CIPD, parsing -json-output result.

  Args:
    cipd_exe: path to cipd client binary to run.
    cmd: cipd subcommand to run.
    args: list of command line arguments to pass to the subcommand.

  Returns:
    (Process exit code, parsed JSON output or None).
  """
  temp_file = None
  try:
    fd, temp_file = tempfile.mkstemp(suffix='.json', prefix='cipd_%s' % cmd)
    os.close(fd)

    cmd_line = [cipd_exe, cmd, '-json-output', temp_file] + list(args)

    print 'Running %s' % ' '.join(cmd_line)
    exit_code = subprocess.call(args=cmd_line, executable=cmd_line[0])
    try:
      with open(temp_file, 'r') as f:
        json_output = json.load(f)
    except (IOError, ValueError):
      json_output = None

    return exit_code, json_output
  finally:
    try:
      if temp_file:
        os.remove(temp_file)
    except OSError:
      pass


def print_title(title):
  """Pretty prints a banner to stdout."""
  sys.stdout.flush()
  sys.stderr.flush()
  print
  print '-' * 80
  print title
  print '-' * 80


def print_go_step_title(title):
  """Same as 'print_title', but also appends values of GOOS and GOARCH."""
  if is_cross_compiling():
    title += '\n' + '-' * 80
    title += '\n  GOOS=%s' % os.environ['GOOS']
    title += '\n  GOARCH=%s' % os.environ['GOARCH']
    if 'GOARM' in os.environ:
      title += '\n  GOARM=%s' % os.environ['GOARM']
  print_title(title)


@contextlib.contextmanager
def hacked_workspace(go_workspace, goos=None, goarch=None):
  """Symlinks Go workspace into new root, modifies os.environ.

  Go toolset embeds absolute paths to *.go files into the executable. Use
  symlink with stable path to make executables independent of checkout path.

  Args:
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    goos: if set, overrides GOOS environment variable (removes it if '').
    goarch: if set, overrides GOARCH environment variable (removes it if '').

  Yields:
    Path where go_workspace is symlinked to.
  """
  new_root = None
  new_workspace = go_workspace
  if not IS_WINDOWS:
    new_root = '/tmp/_chrome_infra_build'
    if os.path.exists(new_root):
      assert os.path.islink(new_root)
      os.remove(new_root)
    os.symlink(GCLIENT_ROOT, new_root)
    rel = os.path.relpath(go_workspace, GCLIENT_ROOT)
    assert not rel.startswith('..'), rel
    new_workspace = os.path.join(new_root, rel)

  orig_environ = os.environ.copy()

  if goos is not None:
    if goos == '':
      os.environ.pop('GOOS', None)
    else:
      os.environ['GOOS'] = goos
  if goarch is not None:
    if goarch == '':
      os.environ.pop('GOARCH', None)
    else:
      os.environ['GOARCH'] = goarch

  # Make sure we build ARMv6 code even if the host is ARMv7. See the comment in
  # get_host_package_vars for reasons why. Also explicitly set GOARM to 6 when
  # cross-compiling (it should be '6' in this case by default anyway).
  plat = platform.machine().lower()
  if plat.startswith('arm') or os.environ.get('GOARCH') == 'arm':
    os.environ['GOARM'] = '6'
  else:
    os.environ.pop('GOARM', None)

  # Debug info (DW_AT_comp_dir attribute in particular) contains current
  # working directory, which by default depends on the build directory, making
  # the build non-deterministic. 'ld' uses os.Getcwd(), and os.Getcwd()'s doc
  # says: "If the current directory can be reached via multiple paths (due to
  # symbolic links), Getwd may return any one of them." It happens indeed. So we
  # can't switch to 'new_workspace'. Switch to '/' instead, cwd is actually not
  # important when building Go code.
  #
  # Protip: To view debug info in an obj file:
  #   gobjdump -g <binary>
  #   gobjdump -g --target=elf32-littlearm <binary>
  # (gobjdump is part of binutils package in Homebrew).

  prev_cwd = os.getcwd()
  if not IS_WINDOWS:
    os.chdir('/')
  try:
    yield new_workspace
  finally:
    os.chdir(prev_cwd)
    # Apparently 'os.environ = orig_environ' doesn't actually modify process
    # environment, only modifications of os.environ object itself do.
    for k, v in orig_environ.iteritems():
      os.environ[k] = v
    for k in os.environ.keys():
      if k not in orig_environ:
        os.environ.pop(k)
    if new_root:
      os.remove(new_root)


def bootstrap_go_toolset(go_workspace):
  """Makes sure go toolset is installed and returns its 'go env' environment.

  Used to verify that our platform detection in get_host_package_vars() matches
  the Go toolset being used.
  """
  with hacked_workspace(go_workspace) as new_workspace:
    print_go_step_title('Making sure Go toolset is installed')
    # env.py does the actual job of bootstrapping if the toolset is missing.
    output = subprocess.check_output(
        args=[
          'python', '-u', os.path.join(new_workspace, get_env_dot_py()),
          'go', 'env',
        ],
        executable=sys.executable)
    # See https://github.com/golang/go/blob/master/src/cmd/go/env.go for format
    # of the output.
    print 'Go environ:'
    print output.strip()
    env = {}
    for line in output.splitlines():
      k, _, v = line.lstrip('set ').partition('=')
      if v.startswith('"') and v.endswith('"'):
        v = v.strip('"')
      env[k] = v
    return env


def run_go_clean(go_workspace, packages, goos=None, goarch=None):
  """Removes object files and executables left from building given packages.

  Transitively cleans all dependencies (including stdlib!) and removes
  executables from GOBIN.

  Args:
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    packages: list of go packages to clean (can include '...' patterns).
    goos: if set, overrides GOOS environment variable (removes it if '').
    goarch: if set, overrides GOARCH environment variable (removes it if '').
  """
  with hacked_workspace(go_workspace, goos, goarch) as new_workspace:
    print_go_step_title('Cleaning:\n  %s' % '\n  '.join(packages))
    subprocess.check_call(
        args=[
          'python', '-u', os.path.join(new_workspace, get_env_dot_py()),
          'go', 'clean', '-i', '-r',
        ] + list(packages),
        executable=sys.executable,
        stderr=subprocess.STDOUT)
    # Above command is either silent (without '-x') or too verbose (with '-x').
    # Prefer silent version, but add a note that it's alright.
    print 'Done.'


def run_go_install(
    go_workspace, packages, rebuild=False, goos=None, goarch=None):
  """Builds (and installs) Go packages into GOBIN via 'go install ...'.

  Compiles and installs packages into default GOBIN, which is <go_workspace>/bin
  (it is setup by go/env.py).

  Args:
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    packages: list of go packages to build (can include '...' patterns).
    rebuild: if True, will forcefully rebuild all dependences.
    goos: if set, overrides GOOS environment variable (removes it if '').
    goarch: if set, overrides GOARCH environment variable (removes it if '').
  """
  rebuild_opt = ['-a'] if rebuild else []
  title = 'Rebuilding' if rebuild else 'Building'
  with hacked_workspace(go_workspace, goos, goarch) as new_workspace:
    print_go_step_title('%s:\n  %s' % (title, '\n  '.join(packages)))
    subprocess.check_call(
        args=[
          'python', '-u', os.path.join(new_workspace, get_env_dot_py()),
          'go', 'install', '-v',
        ] + rebuild_opt + list(packages),
        executable=sys.executable,
        stderr=subprocess.STDOUT)


def run_go_build(
    go_workspace, package, output, rebuild=False, goos=None, goarch=None):
  """Builds single Go package.

  Args:
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    package: go package to build.
    output: where to put the resulting binary.
    rebuild: if True, will forcefully rebuild all dependences.
    goos: if set, overrides GOOS environment variable (removes it if '').
    goarch: if set, overrides GOARCH environment variable (removes it if '').
  """
  rebuild_opt = ['-a'] if rebuild else []
  title = 'Rebuilding' if rebuild else 'Building'
  with hacked_workspace(go_workspace, goos, goarch) as new_workspace:
    print_go_step_title('%s %s' % (title, package))
    subprocess.check_call(
        args=[
          'python', '-u', os.path.join(new_workspace, get_env_dot_py()),
          'go', 'build',
        ] + rebuild_opt + ['-v', '-o', output, package],
        executable=sys.executable,
        stderr=subprocess.STDOUT)


def build_go_code(go_workspace, pkg_defs):
  """Builds and installs all Go packages used by the given PackageDefs.

  Understands GOOS and GOARCH and uses slightly different build strategy when
  cross-compiling. In the end <go_workspace>/bin will have all built binaries,
  and only them (regardless of whether we are cross-compiling or not).

  Args:
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    pkg_defs: list of PackageDef objects that define what to build.
  """
  # Grab a set of all go packages we need to build and install into GOBIN.
  to_install = []
  for p in pkg_defs:
    to_install.extend(p.go_packages)
  to_install = sorted(set(to_install))
  if not to_install:
    return

  # Make sure there are no stale files in the workspace.
  run_go_clean(go_workspace, to_install)

  if not is_cross_compiling():
    # If not cross-compiling, build all Go code in a single "go install" step,
    # it's faster that way. We can't do that when cross-compiling, since
    # 'go install' isn't supposed to be used for cross-compilation and the
    # toolset actively complains with "go install: cannot install cross-compiled
    # binaries when GOBIN is set".
    run_go_install(go_workspace, to_install)
  else:
    # Prebuild stdlib once. 'go build' calls below are discarding build results,
    # so it's better to install as much shared stuff as possible beforehand.
    run_go_install(go_workspace, ['std'])

    # Build packages one by one and put the resulting binaries into GOBIN, as if
    # they were installed there. It's where the rest of the build.py code
    # expects them to be (see also 'root' property in package definition YAMLs).
    go_bin = os.path.join(go_workspace, 'bin')
    exe_suffix = get_package_vars()['exe_suffix']
    for pkg in to_install:
      bin_name = pkg[pkg.rfind('/')+1:] + exe_suffix
      run_go_build(go_workspace, pkg, os.path.join(go_bin, bin_name))


def enumerate_packages(py_venv, package_def_dir, package_def_files):
  """Returns a list PackageDef instances for files in build/packages/*.yaml.

  Args:
    py_env: path to python ENV where to look for YAML parser.
    package_def_dir: path to build/packages dir to search for *.yaml.
    package_def_files: optional list of filenames to limit results to.

  Returns:
    List of PackageDef instances parsed from *.yaml files under packages_dir.
  """
  paths = []
  if not package_def_files:
    # All existing package by default.
    paths = glob.glob(os.path.join(package_def_dir, '*.yaml'))
  else:
    # Otherwise pick only the ones in 'package_def_files' list.
    for name in package_def_files:
      abs_path = os.path.abspath(os.path.join(package_def_dir, name))
      if not os.path.isfile(abs_path):
        raise BuildException('No such package definition file: %s' % name)
      paths.append(abs_path)
  return [PackageDef(p, read_yaml(py_venv, p)) for p in sorted(paths)]


def read_yaml(py_venv, path):
  """Returns content of YAML file as python dict."""
  # YAML lib is in venv, not activated here. Go through hoops.
  # TODO(vadimsh): Doesn't work on ARM, since we have no working infra_python
  # venv there. Replace this hack with vendored pure-python PyYAML.
  oneliner = (
      'import json, sys, yaml; '
      'json.dump(yaml.safe_load(sys.stdin), sys.stdout)')
  if IS_WINDOWS:
    python_venv_path = ('Scripts', 'python.exe')
  else:
    python_venv_path = ('bin', 'python')
  executable = os.path.join(py_venv, *python_venv_path)
  env = os.environ.copy()
  env.pop('PYTHONPATH', None)
  proc = subprocess.Popen(
      [executable, '-c', oneliner],
      executable=executable,
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      env=env)
  with open(path, 'r') as f:
    out, _ = proc.communicate(f.read())
  if proc.returncode:
    raise BuildException('Failed to parse YAML at %s' % path)
  return json.loads(out)


def get_package_vars():
  """Returns a dict with variables that describe the package target environment.

  Variables can be referenced in the package definition YAML as
  ${variable_name}. It allows to reuse exact same definition file for similar
  packages (e.g. packages with same cross platform binary, but for different
  platforms).

  If running in cross-compilation mode, uses GOOS and GOARCH to figure out the
  target platform instead of examining the host environment.
  """
  if is_cross_compiling():
    return get_target_package_vars()
  return get_host_package_vars()


def get_target_package_vars():
  """Returns a dict with variables that describe cross-compilation target env.

  Examines os.environ for GOOS, GOARCH and GOARM.

  The returned dict contains only 'platform' and 'exe_suffix' entries.
  """
  assert is_cross_compiling()
  goos = os.environ['GOOS']
  goarch = os.environ['GOARCH']

  if goarch not in ('386', 'amd64', 'arm', 'arm64', 'mips', 'mips64', 's390x'):
    raise BuildException('Unsupported GOARCH %s' % goarch)

  # There are many ARMs, pick the concrete instruction set. 'v6' is the default,
  # don't try to support other variants for now. Note that 'GOARM' doesn't apply
  # to 'arm64' arch.
  #
  # See:
  #   https://golang.org/doc/install/source#environment
  #   https://github.com/golang/go/wiki/GoArm
  if goarch == 'arm':
    goarm = os.environ.get('GOARM', '6')
    if goarm != '6':
      raise BuildException('Unsupported GOARM value %s' % goarm)
    arch = 'armv6l'
  else:
    arch = goarch

  # We use 'mac' instead of 'darwin'.
  if goos == 'darwin':
    goos = 'mac'

  return {
    'exe_suffix': '.exe' if goos == 'windows' else '',
    'platform': '%s-%s' % (goos, arch),
  }


def get_linux_host_arch():
  """Returns: The Linux host architecture, or None if it could not be resolved.
  """
  try:
    # Query "dpkg" to identify the userspace architecture.
    return subprocess.check_output(['dpkg', '--print-architecture']).strip()
  except OSError:
    # This Linux distribution doesn't use "dpkg".
    return None


def get_host_package_vars():
  """Returns a dict with variables that describe the current host environment.

  The returned platform may not match the machine environment exactly, but it is
  compatible with it.

  For example, on ARMv7 machines we claim that we are in fact running ARMv6
  (which is subset of ARMv7), since we don't really care about v7 over v6
  difference and want to reduce the variability in supported architectures
  instead.

  Similarly, if running on 64-bit Linux with 32-bit user space (based on python
  interpreter bitness), we claim that machine is 32-bit, since most 32-bit Linux
  Chrome Infra bots are in fact running 64-bit kernels with 32-bit userlands.
  """
  # linux, mac or windows.
  platform_variant = {
    'darwin': 'mac',
    'linux2': 'linux',
    'win32': 'windows',
  }.get(sys.platform)
  if not platform_variant:
    raise ValueError('Unknown OS: %s' % sys.platform)

  sys_arch = None
  if sys.platform == 'linux2':
    sys_arch = get_linux_host_arch()

  # If we didn't override our system architecture, identify it using "platform".
  sys_arch = sys_arch or platform.machine()

  # amd64, 386, etc.
  platform_arch = {
    'amd64': 'amd64',
    'i386': '386',
    'i686': '386',
    'x86': '386',
    'x86_64': 'amd64',
    'armv6l': 'armv6l',
    'armv7l': 'armv6l', # we prefer to use older instruction set for builds
  }.get(sys_arch.lower())
  if not platform_arch:
    raise ValueError('Unknown machine arch: %s' % sys_arch)

  # Most 32-bit Linux Chrome Infra bots are in fact running 64-bit kernel with
  # 32-bit userland. Detect this case (based on bitness of the python
  # interpreter) and report the bot as '386'.
  if (platform_variant == 'linux' and
      platform_arch == 'amd64' and
      sys.maxsize == (2 ** 31) - 1):
    platform_arch = '386'

  return {
    # e.g. '.exe' or ''.
    'exe_suffix': EXE_SUFFIX,
    # e.g. 'linux-amd64'
    'platform': '%s-%s' % (platform_variant, platform_arch),
    # e.g. '27' (dots are not allowed in package names).
    'python_version': '%s%s' % sys.version_info[:2],
  }


def is_targeting_windows(pkg_vars):
  """Returns true if 'platform' in pkg_vars indicates Windows."""
  return pkg_vars['platform'].startswith('windows-')


def build_pkg(cipd_exe, pkg_def, out_file, package_vars):
  """Invokes CIPD client to build a package.

  Args:
    cipd_exe: path to cipd client binary to use.
    pkg_def: instance of PackageDef representing this package.
    out_file: where to store the built package.
    package_vars: dict with variables to pass as -pkg-var to cipd.

  Returns:
    {'package': <name>, 'instance_id': <sha1>}

  Raises:
    BuildException on error.
  """
  print_title('Building: %s' % os.path.basename(out_file))

  # Make sure not stale output remains.
  if os.path.isfile(out_file):
    os.remove(out_file)

  # Parse the definition and filter/extend it before passing to CIPD. This
  # process may generate additional files that are put into the package. We
  # delete them afterwards to avoid polluting GOBIN.
  processed_yaml, tmp_files = pkg_def.preprocess(package_vars)

  try:
    # Build the package.
    args = ['-pkg-def', processed_yaml]
    for k, v in sorted(package_vars.items()):
      args.extend(['-pkg-var', '%s:%s' % (k, v)])
    args.extend(['-out', out_file])
    exit_code, json_output = run_cipd(cipd_exe, 'pkg-build', args)
    if exit_code:
      print
      print >> sys.stderr, 'FAILED! ' * 10
      raise BuildException('Failed to build the CIPD package, see logs')

    # Expected result is {'package': 'name', 'instance_id': 'sha1'}
    info = json_output['result']
    print '%s %s' % (info['package'], info['instance_id'])
    return info
  finally:
    for f in [processed_yaml] + tmp_files:
      os.remove(f)


def upload_pkg(cipd_exe, pkg_file, service_url, tags, service_account):
  """Uploads existing *.cipd file to the storage and tags it.

  Args:
    cipd_exe: path to cipd client binary to use.
    pkg_file: path to *.cipd file to upload.
    service_url: URL of a package repository service.
    tags: a list of tags to attach to uploaded package instance.
    service_account: path to *.json file with service account to use.

  Returns:
    {'package': <name>, 'instance_id': <sha1>}

  Raises:
    UploadException on error.
  """
  print_title('Uploading: %s' % os.path.basename(pkg_file))

  args = ['-service-url', service_url]
  for tag in sorted(tags):
    args.extend(['-tag', tag])
  args.extend(['-ref', 'latest'])
  if service_account:
    args.extend(['-service-account-json', service_account])
  args.append(pkg_file)
  exit_code, json_output = run_cipd(cipd_exe, 'pkg-register', args)
  if exit_code:
    print
    print >> sys.stderr, 'FAILED! ' * 10
    raise UploadException('Failed to upload the CIPD package, see logs')
  info = json_output['result']
  print '%s %s' % (info['package'], info['instance_id'])
  return info


def build_cipd_client(go_workspace, out_dir):
  """Builds cipd client binary for the host platform.

  Ignores GOOS and GOARCH env vars. Puts the client binary into
  '<out_dir>/.cipd_client/cipd_<digest>'.

  This binary is used by build.py itself and later by test_packages.py.

  Args:
    go_workspace: path to Go workspace root (contains 'env.py', 'src', etc).
    out_dir: build output directory, will be used to store the binary.

  Returns:
    Path to the built binary.
  """
  # To avoid rebuilding cipd client all the time, we cache it in out/*, using
  # a combination of DEPS+deps.lock+bootstrap.py as a cache key (they define
  # exact set of sources used to build the cipd binary).
  #
  # We can't just use the client in infra.git/cipd/* because it is built by this
  # script itself: it introduced bootstrap dependency cycle in case we need to
  # add a new platform or if we wipe cipd backend storage.
  seed_paths = [
    os.path.join(ROOT, 'DEPS'),
    os.path.join(ROOT, 'go', 'deps.lock'),
    os.path.join(ROOT, 'go', 'bootstrap.py'),
  ]
  digest = hashlib.sha1()
  for p in seed_paths:
    with open(p, 'rb') as f:
      digest.update(f.read())
  cache_key = digest.hexdigest()[:20]

  # Already have it?
  cipd_out_dir = os.path.join(out_dir, '.cipd_client')
  cipd_exe = os.path.join(cipd_out_dir, 'cipd_%s%s' % (cache_key, EXE_SUFFIX))
  if os.path.exists(cipd_exe):
    return cipd_exe

  # Nuke all previous copies, make sure out_dir exists.
  if os.path.exists(cipd_out_dir):
    for p in glob.glob(os.path.join(cipd_out_dir, 'cipd_*')):
      os.remove(p)
  else:
    os.makedirs(cipd_out_dir)

  # Build cipd client binary for the host platform.
  run_go_build(
      go_workspace,
      package='go.chromium.org/luci/cipd/client/cmd/cipd',
      output=cipd_exe,
      rebuild=True,
      goos='',
      goarch='')

  return cipd_exe


def get_build_out_file(package_out_dir, pkg_def):
  """Returns a path where to put built *.cipd package file.

  Args:
    package_out_dir: root directory where to put *.cipd files.
    pkg_def: instance of PackageDef being built.
  """
  # When cross-compiling, append a suffix to package file name to indicate that
  # it's for foreign platform.
  sfx = ''
  if is_cross_compiling():
    sfx = '+' + get_target_package_vars()['platform']
  return os.path.join(package_out_dir, pkg_def.name + sfx + '.cipd')


def run(
    py_venv,
    go_workspace,
    build_callback,
    builder,
    package_def_dir,
    package_out_dir,
    package_def_files,
    build,
    upload,
    service_url,
    tags,
    service_account_json,
    json_output):
  """Rebuilds python and Go universes and CIPD packages.

  Args:
    py_venv: path to 'infra/ENV' or 'infra_internal/ENV'.
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    build_callback: called to build binaries, virtual environment, etc.
    builder: name of CI buildbot builder that invoked the script.
    package_def_dir: path to build/packages dir to search for *.yaml.
    package_out_dir: where to put built packages.
    package_def_files: names of *.yaml files in package_def_dir or [] for all.
    build: False to skip building packages (valid only when upload==True).
    upload: True to also upload built packages, False just to build them.
    service_url: URL of a package repository service.
    tags: a list of tags to attach to uploaded package instances.
    service_account_json: path to *.json service account credential.
    json_output: path to *.json file to write info about built packages to.

  Returns:
    0 on success, 1 or error.
  """
  assert build or upload, 'Both build and upload are False, nothing to do'

  # We need both GOOS and GOARCH or none.
  if is_cross_compiling():
    if not os.environ.get('GOOS') or not os.environ.get('GOARCH'):
      print >> sys.stderr, (
          'When cross-compiling both GOOS and GOARCH environment variables '
          'must be set.')
      return 1
    if os.environ.get('GOARM', '6') != '6':
      print >> sys.stderr, 'Only GOARM=6 is supported for now.'
      return 1

  # Append tags related to the build host. They are especially important when
  # cross-compiling: cross-compiled packages can be identified by comparing the
  # platform in the package name with value of 'build_host_platform' tag.
  tags = list(tags)
  host_vars = get_host_package_vars()
  tags.append('build_host_hostname:' + socket.gethostname().split('.')[0])
  tags.append('build_host_platform:' + host_vars['platform'])

  all_packages = enumerate_packages(py_venv, package_def_dir, package_def_files)
  packages_to_build = [p for p in all_packages if p.should_build(builder,
                                                                 host_vars)]

  print_title('Overview')
  if upload:
    print 'Service URL: %s' % service_url
    print
  if builder:
    print 'Package definition files to process on %s:' % builder
  else:
    print 'Package definition files to process:'
  for pkg_def in packages_to_build:
    print '  %s' % pkg_def.name
  if not packages_to_build:
    print '  <none>'
  print
  print 'Variables to pass to CIPD:'
  package_vars = get_package_vars()
  for k, v in sorted(package_vars.items()):
    print '  %s = %s' % (k, v)
  if upload and tags:
    print
    print 'Tags to attach to uploaded packages:'
    for tag in sorted(tags):
      print '  %s' % tag
  if not packages_to_build:
    print
    print 'Nothing to do.'
    return 0

  # Remove old build artifacts to avoid stale files in case the script crashes
  # for some reason.
  if build:
    print_title('Cleaning %s' % package_out_dir)
    if not os.path.exists(package_out_dir):
      os.makedirs(package_out_dir)
    cleaned = False
    for pkg_def in packages_to_build:
      out_file = get_build_out_file(package_out_dir, pkg_def)
      if os.path.exists(out_file):
        print 'Removing stale %s' % os.path.basename(out_file)
        os.remove(out_file)
        cleaned = True
    if not cleaned:
      print 'Nothing to clean'

  # Make sure we have a Go toolset and it matches the host platform we detected
  # in get_host_package_vars(). Otherwise we may end up uploading wrong binaries
  # under host platform CIPD package suffix. It's important on Linux with 64-bit
  # kernel and 32-bit userland (we must use 32-bit Go in that case, even if
  # 64-bit Go works too).
  go_env = bootstrap_go_toolset(go_workspace)
  expected_arch = host_vars['platform'].split('-')[1]
  if go_env['GOHOSTARCH'] != expected_arch:
    print >> sys.stderr, (
        'Go toolset GOHOSTARCH (%s) doesn\'t match expected architecture (%s)' %
        (go_env['GOHOSTARCH'], expected_arch))
    return 1

  # Build the cipd client needed later to build or upload packages.
  cipd_exe = build_cipd_client(go_workspace, package_out_dir)

  # Build the world.
  if build:
    build_callback(packages_to_build)

  # Package it.
  failed = []
  succeeded = []
  for pkg_def in packages_to_build:
    out_file = get_build_out_file(package_out_dir, pkg_def)
    try:
      info = None
      if build:
        info = build_pkg(cipd_exe, pkg_def, out_file, package_vars)
      if upload:
        if pkg_def.uses_python_env and not builder:
          print ('Not uploading %s, since it uses a system Python enviornment '
                 'and that enviornment is only valid on builders.' % (
                   pkg_def.name,))
          continue

        info = upload_pkg(
            cipd_exe,
            out_file,
            service_url,
            tags,
            service_account_json)
      assert info is not None
      succeeded.append({'pkg_def_name': pkg_def.name, 'info': info})
    except (BuildException, UploadException) as e:
      failed.append({'pkg_def_name': pkg_def.name, 'error': str(e)})

  print_title('Summary')
  for d in failed:
    print 'FAILED %s, see log above' % d['pkg_def_name']
  for d in succeeded:
    print '%s %s' % (d['info']['package'], d['info']['instance_id'])

  if json_output:
    with open(json_output, 'w') as f:
      summary = {
        'failed': failed,
        'succeeded': succeeded,
        'tags': sorted(tags),
        'vars': package_vars,
      }
      json.dump(summary, f, sort_keys=True, indent=2, separators=(',', ': '))

  return 1 if failed else 0


def build_infra(pkg_defs):
  """Builds infra.git multiverse.

  Args:
    pkg_defs: list of PackageDef instances for packages being built.
  """
  # Skip building python if not used or if cross-compiling.
  if any(p.uses_python_env for p in pkg_defs) and not is_cross_compiling():
    print_title('Making sure python virtual environment is fresh')
    run_python(
        script=os.path.join(ROOT, 'bootstrap', 'bootstrap.py'),
        args=[
          '--deps_file',
          os.path.join(ROOT, 'bootstrap', 'deps.pyl'),
          os.path.join(ROOT, 'ENV'),
        ])
  # Build all necessary go binaries.
  build_go_code(os.path.join(ROOT, 'go'), pkg_defs)


def main(
    args,
    build_callback=build_infra,
    py_venv=os.path.join(ROOT, 'ENV'),
    go_workspace=os.path.join(ROOT, 'go'),
    package_def_dir=os.path.join(ROOT, 'build', 'packages'),
    package_out_dir=os.path.join(ROOT, 'build', 'out')):
  parser = argparse.ArgumentParser(description='Builds infra CIPD packages')
  parser.add_argument(
      'yamls', metavar='YAML', type=str, nargs='*',
      help='name of a file in build/packages/* with the package definition')
  parser.add_argument(
      '--upload',  action='store_true', dest='upload', default=False,
      help='upload packages into the repository')
  parser.add_argument(
      '--no-rebuild',  action='store_false', dest='build', default=True,
      help='when used with --upload means upload existing *.cipd files')
  parser.add_argument(
      '--builder', metavar='NAME', type=str,
      help='Name of the CI buildbot builder that invokes this script.')
  parser.add_argument(
      '--service-url', metavar='URL', dest='service_url',
      default=PACKAGE_REPO_SERVICE,
      help='URL of the package repository service to use')
  parser.add_argument(
      '--service-account-json', metavar='PATH', dest='service_account_json',
      help='path to credentials for service account to use')
  parser.add_argument(
      '--json-output', metavar='PATH', dest='json_output',
      help='where to dump info about built package instances')
  parser.add_argument(
      '--tags', metavar='KEY:VALUE', type=str, dest='tags', nargs='*',
      help='tags to attach to uploaded package instances')
  args = parser.parse_args(args)
  if not args.build and not args.upload:
    parser.error('--no-rebuild doesn\'t make sense without --upload')
  return run(
      py_venv,
      go_workspace,
      build_callback,
      args.builder,
      package_def_dir,
      package_out_dir,
      [n + '.yaml' if not n.endswith('.yaml') else n for n in args.yamls],
      args.build,
      args.upload,
      args.service_url,
      args.tags or [],
      args.service_account_json,
      args.json_output)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
