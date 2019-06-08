#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"
DEPS_PREFIX="$2"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# Determine our Python interpreter version. It will use PEP440's "local
# version identifier" to specify a local Python version based on our
# $PATCH_VERSION.
PY_VERSION="$_3PP_VERSION+${_3PP_PATCH_VERSION}"

CFLAGS="-I$DEPS_PREFIX/include"
CPPFLAGS="-I$DEPS_PREFIX/include"
LDFLAGS="-L$DEPS_PREFIX/lib"

export CONFIG_ARGS="--host $CROSS_TRIPLE"

# This module is broken, and seems to reference a non-existent symbol
# at compile time.
SETUP_LOCAL_SKIP=(_testcapi)
SETUP_LOCAL_ATTACH=(
  "$DEPS_PREFIX/lib/libbz2.a"
  "$DEPS_PREFIX/lib/libreadline.a"
  "$DEPS_PREFIX/lib/libpanelw.a"
  "$DEPS_PREFIX/lib/libncursesw.a"
  "$DEPS_PREFIX/lib/libsqlite3.a"
  "$DEPS_PREFIX/lib/libz.a"
  "$DEPS_PREFIX/lib/liblzma.a"
  "$DEPS_PREFIX/lib/libssl.a"
  "$DEPS_PREFIX/lib/libcrypto.a"
  "$DEPS_PREFIX/lib/libffi.a"
  "$DEPS_PREFIX/lib/libuuid.a"

  # We always use the OSS ncurses headers; on OS X the system headers are weird
  # and python's configure file works around that by not setting the
  # XOPEN_SOURCE defines. Unfortunately that means that on OS X the configure
  # script gets it wrong.
  #
  # We set the NCURSES_WIDECHAR variable explicitly, as that's the only intended
  # side effect of setting the XOPEN_SOURCE defines. Setting XOPEN_SOURCE
  # defines ourselves leads to problems in other headers which we still use :(.
  "_curses:: -DNCURSES_WIDECHAR=1"
  "_curses_panel:: -DNCURSES_WIDECHAR=1"
)

if [[ $_3PP_PLATFORM == mac* ]]; then
  PYTHONEXE=python.exe

  # Instruct Mac to prefer ".a" files in earlier library search paths
  # rather than search all of the paths for a ".dylib" and then, failing
  # that, do a second sweep for ".a".
  LDFLAGS="$LDFLAGS -Wl,-search_paths_first"

  # Our builder system is missing X11 headers, so this module does not build.
  SETUP_LOCAL_SKIP+=(_tkinter)
else
  PYTHONEXE=python

  EXTRA_CONFIGURE_ARGS="--with-fpectl --with-dbmliborder=bdb:gdbm"
  # NOTE: This can break building on Mac builder, causing it to freeze
  # during execution.
  #
  # Maybe look into this if we have time later.
  EXTRA_CONFIGURE_ARGS="$EXTRA_CONFIGURE_ARGS --enable-optimizations"

  # TODO(iannucci) This assumes we're building for linux under docker (which is
  # currently true).
  EXTRA_CONFIGURE_ARGS="$EXTRA_CONFIGURE_ARGS --build=x86_64-linux-gnu"

  # OpenSSL 1.1.1 depends on pthread, so it needs to come LAST. Python's
  # Makefile has an LDLAST to allow some ldflags to be the very last thing on
  # the link line.
  LDLAST="-lpthread"

  # The "crypt" module needs to link against glibc's "crypt" function.
  #
  # TODO: Maybe consider implementing a static version using OpenSSL and
  # linking that in instead?
  SETUP_LOCAL_ATTACH+=('_crypt::-lcrypt')

  # On Linux, we will statically compile OpenSSL into the binary, since we
  # want to be generally system/library agnostic.
  SETUP_LOCAL_ATTACH+=(
    "$DEPS_PREFIX/lib/libnsl.a"
  )

  # On Linux, we need to ensure that most symbols from our static-embedded
  # libraries (notably OpenSSL) don't get exported. If they do, they can
  # conflict with the same libraries from wheels or other dynamically
  # linked sources.
  #
  # This set of symbols was determined by trial, see:
  # - crbug.com/763792
  LDFLAGS="$LDFLAGS -Wl,--version-script=$SCRIPT_DIR/gnu_version_script.txt"

  # Assert blindly that the target distro will have /dev/ptmx and not /dev/ptc.
  # This is likely to be true, since all linuxes that we know of have this
  # configuration.
  export ac_cv_file__dev_ptmx=y
  export ac_cv_file__dev_ptc=n
fi

# Python tends to hard-code /usr/include and /usr/local/include in its setup.py
# file which can end up picking up headers and stuff from wherever.
sed -i \
  "s+/usr/include+$DEPS_PREFIX/include+" \
  setup.py
sed -i \
  "s+/usr/include+$DEPS_PREFIX/include+" \
  configure.ac
sed -i \
  "s+/usr/local/include+$DEPS_PREFIX/include+" \
  setup.py
sed -i \
  "s+/usr/lib+$DEPS_PREFIX/lib+" \
  setup.py

# Generate our configure script.
autoconf

export LDFLAGS
export CPPFLAGS
export LDLAST
# Configure our production Python build with our static configuration
# environment and generate our basic platform.
#
# We're going to use our bootstrap python interpreter to generate our static
# module list.
./configure --prefix "$PREFIX" --host="$CROSS_TRIPLE" \
  --disable-shared --without-system-ffi --enable-ipv6 \
  --enable-py-version-override="$PY_VERSION" \
  --with-openssl="$DEPS_PREFIX" --with-libs="-lrt -pthread" \
  $EXTRA_CONFIGURE_ARGS

export LDFLAGS=
export CPPFLAGS=
export LDLAST=

# Tweak Makefile to change LIBFFI_INCLUDEDIR=<TAB>path
sed -i \
  $'s+^LIBFFI_INCLUDEDIR=\t.*+LIBFFI_INCLUDEDIR=\t'"$DEPS_PREFIX/include+" \
  Makefile

# Generate our "pybuilddir.txt" file. This also generates
# "_sysconfigdata.py" from our current Python, which we need to
# generate our module list, since it includes our "configure_env"'s
# CPPFLAGS, LDFLAGS, etc.
make platform

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
SETUP_LOCAL_FLAGS=()
for x in "${SETUP_LOCAL_SKIP[@]}"; do
  SETUP_LOCAL_FLAGS+=(--skip "$x")
done
for x in "${SETUP_LOCAL_ATTACH[@]}"; do
  SETUP_LOCAL_FLAGS+=(--attach "$x")
done

INTERP=python3
if [[ $_3PP_PLATFORM == $_3PP_TOOL_PLATFORM ]]; then  # not cross compiling
  INTERP=./$PYTHONEXE
fi

$INTERP -s -S "$SCRIPT_DIR/python_mod_gen.py" \
  --pybuilddir $(cat pybuilddir.txt) \
  --output ./Modules/Setup.local \
  "${SETUP_LOCAL_FLAGS[@]}"

# Build production Python.
make install

# Augment the Python installation.

# Read / augment / write the "ssl.py" module to implement custom SSL
# certificate loading logic.
#
# We do this here instead of "usercustomize.py" because the latter
# isn't propagated when a VirtualEnv is cut.
cat "$SCRIPT_DIR/python_ssl_suffix.py3" >> $PREFIX/lib/python*/ssl.py

# TODO: maybe strip python executable?

$INTERP `which pip_bootstrap.py` "$PREFIX"

PYTHON_MAJOR=$(cd $PREFIX/lib && echo python*)

# Cleanup!
find $PREFIX -name '*.a' -delete -print
# For some reason, docker freezes when doing `rm -rf .../test`. Specifically,
# `rm` hangs at 100% CPU forever on my mac. However, deleting it in smaller
# chunks works just fine. IDFK.
find $PREFIX/lib/$PYTHON_MAJOR/test -type f -exec rm -vf '{}' ';'
rm -vrf $PREFIX/lib/$PYTHON_MAJOR/test
rm -vrf $PREFIX/lib/$PYTHON_MAJOR/config
rm -vrf $PREFIX/lib/pkgconfig
rm -vrf $PREFIX/share
rm -vrf $PREFIX/lib/$PYTHON_MAJOR/lib-dynload/*.{so,dylib} || true
touch $PREFIX/lib/$PYTHON_MAJOR/lib-dynload/.keep
