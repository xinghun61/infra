#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

if ! which realpath; then
  realpath() {
    python -c "import os, sys; print os.path.realpath(sys.argv[1])" "$@"
  }
fi > /dev/null

# The "ncurses" package, by default, uses a fixed-path location for terminal
# information. This is not relocatable, so we need to disable it. Instead, we
# will compile ncurses with a set of hand-picked custom terminal information
# data baked in, as well as the ability to probe terminal via termcap if
# needed.
#
# To do this, we need to build in multiple stages:
# 1) Generic configure / make so that the "tic" (terminfo compiler) and
#    "toe" (table of entries) commands are built.
# 2) Use "toe" tool to dump the set of available profiles and groom it.
# 3) Build library with no database support using "tic" from (1), and
#    configure it to statically embed all of the profiles from (2).
tic_build=$(realpath ../tic_build)
tic_prefix=$(realpath ../tic_prefix)

# Make tic for host
(
  if [[ "$_3PP_PLATFORM" != "$_3PP_TOOL_PLATFORM" ]]; then
    . /install-util.sh
    toggle_host

    # TODO(iannucci): fix toggle_host to correctly set $CC to gcc-4.9. This is
    # because the docker images currently set an alternative for `cc` and `gcc`
    # in /usr/bin to be the xcompile gcc. None of the other tools in /usr/bin
    # are switched though...
    export CC=gcc-4.9
  fi

  src=$(realpath .)
  mkdir -p $tic_build
  cd $tic_build

  "$src/configure" --enable-termcap --prefix "$tic_prefix" || cat "$tic_build/config.log"
  make install -j $(nproc)
)

# Run toe to strip out fallbacks with bugs.
#
# This currently leaves 1591 profiles behind, which will be statically
# compiled into the library.
#
# Some profiles do not generate valid C, either because:
# - They begin with a number, which is not valid in C.
# - They are flattened to a duplicate symbol as another profile. This
#   usually happens when there are "+" and "-" variants; we choose
#   "-".
# - They include quotes in the description name.
#
# None of these identified terminals are really important, so we will
# just avoid processing them.
fallback_exclusions=(
  9term
  guru\\+
  hp\\+
  tvi912b\\+
  tvi912b-vb
  tvi920b-vb
  att4415\\+
  nsterm\\+
  xnuppc\\+
  xterm\\+
  wyse-vp
)
joined=$(IFS='|'; echo "${fallback_exclusions[*]}")
fallbacks_array=($($tic_prefix/bin/toe | awk '{print $1}' | grep -Ev "^(${joined})"))
fallbacks=$(IFS=','; echo "${fallbacks_array[*]}")

# Run the remainder of our build with our generated "tic" on PATH.
#
# Note that we only run "install.libs". Standard "install" expects the
# full database to exist, and this will not be the case since we are
# explicitly disabling it.
PATH=$tic_prefix/bin:$PATH ./configure \
  --prefix=$PREFIX \
  --host=$CROSS_TRIPLE \
  --disable-database \
  --disable-db-install \
  --enable-termcap \
  --with-fallbacks="$fallbacks"
make clean

# Build everything to get the timestamps warmed up. This will then fail to
# generate comp_captab.c (or init_keytry.h, depending on the race).
make install.libs -j $(nproc) || (
  # Then copy the good toolchain programs from $tic_build that we built earlier.
  cp $tic_build/ncurses/make_* ./ncurses
  # Huzzah, cross compiling C is terrible.
  make install.libs -j $(nproc)
)

# Some programs (like python) expect to be able to `#include <ncurses.h>`, so
# create that symlink. Ncurses also installs the actual header as `curses.h`
# (and creates a symlink for ncurses.h), so we link to the original file here.
(cd $PREFIX/include && ln -s ./ncurses/curses.h ncurses.h)
(cd $PREFIX/include && ln -s ./ncurses/panel.h panel.h)
(cd $PREFIX/include && ln -s ./ncurses/term.h term.h)
