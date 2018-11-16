#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

# The commandline for lessmsi is a bit weird. We MUST provide an absolute
# windows path which ends with slash in order for it to extract to our present
# location. Otherwise it will assume we're passing it a path of a file in the
# msi archive that we want to extract.
lessmsi x install.msi $(cygpath -w $(pwd))"\\"

rm -vrf SourceDir/Windows
rm -vrf SourceDir/tcl
rm -vrf SourceDir/Doc
rm -vrf SourceDir/DLLs/tcl*.*
rm -vrf SourceDir/DLLs/tk*.*
rm -vrf SourceDir/include
rm -vrf SourceDir/libs
rm -vrf SourceDir/Lib/test
rm -vrf SourceDir/Lib/tkinter
rm -vrf SourceDir/Tools/Scripts

mkdir "$PREFIX/bin"
mv SourceDir/* "$PREFIX/bin"

"$PREFIX/bin/python.exe" $(where pip_bootstrap.py) "$PREFIX/bin"
# This is full of .exe shims which don't work correctly unless you put
# python.exe on %PATH% (via a hack in pip_bootstrap.py). Currently (2018/11/12)
# we don't put python.exe on %PATH% for devs, and we don't use these shims on
# bots.
#
# Rather than have a folder full of maybe-broken exes, we remove them here.
#
# However, when https://bitbucket.org/vinay.sajip/simple_launcher/issues/4 is
# fixed, we can stop doing this (but will maybe have to tweak pip_bootstrap
# somehow to take advantage of the new syntax).
rm -vrf "$PREFIX/bin/Scripts"
