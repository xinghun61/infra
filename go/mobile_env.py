#!/usr/bin/env vpython
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Like env.py, but for building go-on-mobile.

It wraps env.py, runs `gomobile init`, and adds mobile-specific env vars.
"""

assert __name__ == '__main__'

import os
import pipes
import platform
import subprocess
import sys


ANDROID_NDK_PATH = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), '.vendor', 'pkg', 'gomobile',
    'android-ndk-r12b')

# Used for mapping GOARCH values to (NDK toolset directory, compiler name)
ANDROID_TOOLSETS = {
  'arm': ('arm', 'arm-linux-androideabi-clang'),
  'arm64': ('arm64', 'aarch64-linux-android-clang'),
  '386': ('x86', 'i686-linux-android-clang'),
  'amd64': ('x86_64', 'x86_64-linux-android-clang'),
}



def _get_android_env(env):
  """Adds GO* and C* environment variables needed for building for android."""
  if platform.system() != 'Linux':
    raise Exception(
        'Only Linux hosts supported for android cross-compiling')

  arch = env.get('GOARCH')
  if arch not in ANDROID_TOOLSETS:
    raise Exception(
        'Specified arch not currently supported on android: %s' % arch)

  toolset_dir, compiler = ANDROID_TOOLSETS[arch]

  # Needed when cross-compiling uses of cgo.
  env['CGO_ENABLED'] = '1'
  env['CC'] = os.path.join(
      ANDROID_NDK_PATH, toolset_dir, 'bin', compiler)
  env['CXX'] = os.path.join(
      ANDROID_NDK_PATH, toolset_dir, 'bin', compiler + '++')

  # Compiler/linker needs access to android system headers in the NDK.
  sysroot_path = os.path.join(ANDROID_NDK_PATH, toolset_dir, 'sysroot')
  env['CGO_CFLAGS'] = '-I %s/usr/include --sysroot %s' % (
      sysroot_path, sysroot_path)
  env['CGO_LDFLAGS'] = '-L %s/usr/lib --sysroot %s' % (
      sysroot_path, sysroot_path)


# Run `gomobile init` to fetch the android NDK.
cwd = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(ANDROID_NDK_PATH):
  cmd = [sys.executable, 'env.py', 'gomobile', 'init']
  subprocess.check_call(cmd, cwd=cwd)

# Keep track of any changed env vars for printing to stdout later.
old = os.environ.copy()
new = os.environ.copy()
if 'android' in old.get('GOOS', ''):
  _get_android_env(new)

cwd = os.path.dirname(os.path.realpath(__file__))
if len(sys.argv) == 1:
  cmd = [sys.executable, 'env.py']
  print subprocess.check_output(cmd, env=new, cwd=cwd).strip()
  for key, value in sorted(new.iteritems()):
    if old.get(key) != value:
      print 'export %s=%s' % (key, pipes.quote(value))
else:
  cmd = [sys.executable, 'env.py']
  cmd.extend(sys.argv[1:])
  sys.exit(subprocess.call(cmd, env=new, cwd=cwd))
