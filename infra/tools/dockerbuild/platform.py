# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections


class Platform(collections.namedtuple('Platform', (
    'name', # The name of the platform.
    'manylinux_name', # If the platform is "manylinux', the "manylinux" Docker
                      # image build name (e.g., "cp27-cp27mu").
    'wheel_abi', # The Python wheel ABI.
    'wheel_plat', # Tuple of Python wheel platforms. Must have at least one.
    'dockcross_base', # The "dockcross" base image (can be None).
    'openssl_target', # The OpenSSL "Configure" script build target.
    'packaged', # Do Python wheels get packaged on PyPi for this platform?
    'cipd_platform', # The name of the CIPD platform to use.
    ))):

  @property
  def dockcross_base_image(self):
    if not self.dockcross_base:
      return None
    return 'dockcross/%s' % (self.dockcross_base,)

  @property
  def dockcross_image_tag(self):
    return 'infra-dockerbuild-%s' % (self.name,)


ALL = {p.name: p for p in (
    Platform(
        name='linux-armv6',
        manylinux_name=None,
        wheel_abi='cp27mu',
        wheel_plat=('linux_armv6l',),
        dockcross_base='linux-armv6',
        openssl_target='linux-armv4',
        packaged=False,
        cipd_platform='linux-armv6l',
    ),

    Platform(
        name='linux-armv7',
        manylinux_name=None,
        wheel_abi='cp27mu',
        wheel_plat=('linux_armv7l',),
        dockcross_base='linux-armv7',
        openssl_target='linux-armv4',
        packaged=False,

        # NOTE: CIPD categorizes all 32-bit ARM as "armv6l".
        cipd_platform='linux-armv6l',
    ),

    Platform(
        name='linux-arm64',
        manylinux_name=None,
        wheel_abi='cp27mu',
        wheel_plat=('linux_arm64', 'linux_aarch64'),
        dockcross_base='linux-arm64',
        openssl_target='linux-aarch64',
        packaged=False,
        cipd_platform='linux-arm64',
    ),

    Platform(
        name='linux-mipsel',
        manylinux_name=None,
        wheel_abi='cp27mu',
        wheel_plat=('linux_mipsel',),
        dockcross_base='linux-mipsel',
        openssl_target='linux-mips32',
        packaged=False,
        cipd_platform='linux-mips32',
    ),

    # NOTE: "mips" and "mips64" both use 32-bit MIPS, which is consistent with
    # our devices.
    Platform(
        name='linux-mips',
        manylinux_name=None,
        wheel_abi='cp27mu',
        wheel_plat=('linux_mips',),
        dockcross_base='linux-mips',
        openssl_target='linux-mips32',
        packaged=False,
        cipd_platform='linux-mips',
    ),
    Platform(
        name='linux-mips64',
        manylinux_name=None,
        wheel_abi='cp27mu',
        wheel_plat=('linux_mips64',),
        dockcross_base='linux-mips',
        openssl_target='linux-mips32',
        packaged=False,
        cipd_platform='linux-mips64',
    ),

    Platform(
        name='manylinux-x64',
        manylinux_name='cp27-cp27mu',
        wheel_abi='cp27mu',
        wheel_plat=('manylinux1_x86_64',),
        dockcross_base='manylinux-x64',
        openssl_target='linux-x86_64',
        packaged=True,
        cipd_platform='linux-amd64',
    ),

    # Atypical but possible Python configuration using "2-byte UCS", with
    # ABI "cp27m".
    Platform(
        name='manylinux-x64-ucs2',
        manylinux_name='cp27-cp27m',
        wheel_abi='cp27m',
        wheel_plat=('manylinux1_x86_64',),
        dockcross_base='manylinux-x64',
        openssl_target='linux-x86_64',
        packaged=True,
        cipd_platform='linux-amd64',
    ),

    Platform(
        name='manylinux-x86',
        manylinux_name='cp27-cp27mu',
        wheel_abi='cp27mu',
        wheel_plat=('manylinux1_i686',),
        dockcross_base='manylinux-x86',
        openssl_target='linux-x86',
        packaged=True,
        cipd_platform='linux-386',
    ),

    # Atypical but possible Python configuration using "2-byte UCS", with
    # ABI "cp27m".
    Platform(
        name='manylinux-x86-ucs2',
        manylinux_name='cp27-cp27m',
        wheel_abi='cp27m',
        wheel_plat=('manylinux1_i686',),
        dockcross_base='manylinux-x86',
        openssl_target='linux-x86',
        packaged=True,
        cipd_platform='linux-386',
    ),

    Platform(
        name='mac-x64',
        manylinux_name=None,
        wheel_abi='cp27m',
        wheel_plat=('macosx_10_10_intel',),
        dockcross_base=None,
        openssl_target='darwin64-x86_64-cc',
        packaged=True,
        cipd_platform='mac-amd64',
    ),

    Platform(
        name='windows-x86',
        manylinux_name=None,
        wheel_abi='cp27m',
        wheel_plat=('win32',),
        dockcross_base=None,
        openssl_target='Cygwin-x86',
        packaged=True,
        cipd_platform='windows-386',
    ),

    Platform(
        name='windows-x64',
        manylinux_name=None,
        wheel_abi='cp27m',
        wheel_plat=('win_amd64',),
        dockcross_base=None,
        openssl_target='Cygwin-x86_64',
        packaged=True,
        cipd_platform='windows-amd64',
    ),

)}
NAMES = sorted(ALL.keys())
PACKAGED = set(p for p in ALL.itervalues() if p.packaged)

# Represents the "universal package" platform.
UNIVERSAL = Platform(
    name='universal',
    manylinux_name=None,
    wheel_abi='none',
    wheel_plat=('any',),
    dockcross_base=None,
    openssl_target=None,
    packaged=True,
    cipd_platform=None,
)
