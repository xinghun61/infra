// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"go.chromium.org/luci/vpython/api/vpython"
)

var verificationScenarios = []*vpython.PEP425Tag{
	{"cp27", "cp27mu", "manylinux1_i686"},
	{"cp27", "cp27mu", "manylinux1_x86_64"},
	{"cp27", "cp27mu", "linux_arm64"},
	{"cp27", "cp27mu", "linux_mips64"},

	// NOTE: CIPD generalizes "platform" to "armv6l" even on armv7l platforms.
	{"cp27", "cp27mu", "linux_armv6l"},
	{"cp27", "cp27mu", "linux_armv7l"},

	{"cp27", "cp27m", "macosx_10_10_intel"},

	{"cp27", "cp27m", "win32"},
	{"cp27", "cp27m", "win_amd64"},
}
