// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"golang.org/x/net/context"

	"go.chromium.org/luci/vpython/api/vpython"
	"go.chromium.org/luci/vpython/application"
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

// verificationGen is an application.VerificationFunc which will generate
// verification scenarios for infra-supported package combinations.
func withVerificationConfig(c context.Context, fn func(application.Config, []*vpython.PEP425Tag) error) error {
	// Clone our default package loader and configure it for verification.
	plBase := cipdPackageLoader
	plBase.Template = func(c context.Context, e *vpython.Environment) (map[string]string, error) {
		if len(e.Pep425Tag) == 0 {
			return nil, nil
		}
		return getPEP425CIPDTemplateForTag(e.Pep425Tag[0])
	}

	// Build an alternative Config with that set.
	vcfg := defaultConfig
	vcfg.PackageLoader = &plBase

	return fn(vcfg, verificationScenarios)
}
