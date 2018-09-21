#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"
DEPS="$2"

CPPFLAGS="-I${DEPS}/include"
LDFLAGS="-flto -L$DEPS/lib"
CFLAGS="-flto"

# Write the "version" file. This is used by the "GIT-VERSION-GEN" script to pull
# the Git version. We name ours after the Git tag that we pulled and our
# Chromium-specific suffix, e.g.: v2.12.2.chromium4
echo v$_3PP_VERSION.$_3PP_PATCH_VERSION > version

# Override the autoconfig / system Makefile entries with custom ones.
cat > config.mak <<EOF
# "RUNTIME_PREFIX" configures Git to be relocatable. This allows it to
# be bundled and deployed to arbitrary paths.
#
# The other variables configure Git to enable and use relative runtime
# paths.
RUNTIME_PREFIX=YesPlease
gitexecdir=libexec/git-core
template_dir=share/git-core/templates
sysconfdir=etc

# CIPD doesn't support hardlinks, so hardlinks become copies of the
# original file. Use symlinks instead.
NO_INSTALL_HARDLINKS=YesPlease

# We disable "GECOS" detection. This will make the default commit user
# name potentially less pretty, but this is acceptable, since users and
# bots should both be setting that value.
NO_GECOS_IN_PWENT=YesPlease

# We always supply "curl", so override any automatic detection.
NO_CURL=
EOF

if [[ $OSTYPE = darwin* ]]; then
  # Several functions are declared in OSX headers that aren't actually
  # present in its standard libraries. Autoconf will succeed at detecting
  # them, only to fail later due to a linker error. Override these autoconf
  # variables via env to prevent this.
  export ac_cv_func_getentropy=n
  export ac_cv_func_clock_gettime=n

  # Linking "libcurl" using "--with-darwinssl" requires that we include
  # the Foundation and Security frameworks.
  LDFLAGS="$LDFLAGS -framework Foundation -framework Security"
  # Include "libpcre2" path in LDFLAGS so the autoconf script will detect it.
  LDFLAGS="$LDFLAGS -lpcre2-8"
  # We have to force our static libraries into linking to prevent it from
  # linking dynamic or, worse, not seeing them at all.
  LDFLAGS="$LDFLAGS -lz -lcurl"
else
  # Since we're supplying these libraries, we need to explicitly include them in
  # our LIBS (for "configure" probing) and our Makefile on Linux.
  #
  # Normally we'd use the LIBS environment variable for both, but that doesn't
  # make its way to the Makefile (bug?). Therefore, the most direct way to do
  # this is to find the line in Git's "Makefile" that initializes EXTLIBS and
  # add the dependent libraries to it :(
  LIBS="-lcurl -ldl -lpthread -lz -lidn2 -lssl -lcrypto -lpcre2-8"
  cat >> config.mak <<EOF
EXTLIBS = $LIBS
EOF
fi


export CPPFLAGS
export CFLAGS
export LDFLAGS
export LIBS

make configure
./configure --host="$CROSS_TRIPLE" --prefix="$PREFIX" --with-libpcre2
make install -j$(nproc)
