// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"path/filepath"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/vpython/api/vpython"
	"github.com/luci/luci-go/vpython/application"

	"github.com/luci/luci-go/common/system/filesystem"
)

var verificationScenarios = []*vpython.Pep425Tag{
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
func withVerificationConfig(c context.Context, fn func(application.Config, []*vpython.Pep425Tag) error) error {
	// Run verification within the scope of a tempdir. We use an explicit tempdir
	// for caching so our verification resolves everything against the live CIPD
	// service. We will, however, share a cache directory and root in between
	// verification rounds so that we can cache duplicate lookups.
	td := filesystem.TempDir{
		Prefix: "vpython_verification",
	}
	return td.With(func(tdir string) error {
		// Clone our default package loader and configure it for verification.
		plBase := cipdPackageLoader
		plBase.Options.CacheDir = filepath.Join(tdir, "cache")
		plBase.Options.Root = filepath.Join(tdir, "root")
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
	})
}
