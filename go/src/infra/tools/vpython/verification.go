// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"path/filepath"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/system/filesystem"
	"github.com/luci/luci-go/vpython/api/vpython"
	"github.com/luci/luci-go/vpython/application"
	"github.com/luci/luci-go/vpython/cipd"
)

// verificationGen is an application.VerificationFunc which will generate
// verification scenarios for infra-supported package combinations.
func verificationGen(c context.Context, vf application.VerificationFunc) {
	tag := func(version, abi, arch string) *vpython.Environment_Pep425Tag {
		return &vpython.Environment_Pep425Tag{
			Version: version,
			Abi:     abi,
			Arch:    arch,
		}
	}

	// Define our verification scenarios.
	scenarios := []verificationScenario{
		{"linux", "386", tag("cp27", "cp27mu", "manylinux1_i686")},
		{"linux", "amd64", tag("cp27", "cp27mu", "manylinux1_x86_64")},
		{"linux", "arm64", tag("cp27", "cp27mu", "linux_arm64")},
		{"linux", "mips64", tag("cp27", "cp27mu", "linux_mips64")},

		// NOTE: CIPD generalizes "platform" to "armv6l" even on armv7l platforms.
		{"linux", "armv6l", tag("cp27", "cp27mu", "linux_armv6l")},
		{"linux", "armv6l", tag("cp27", "cp27mu", "linux_armv7l")},

		{"mac", "amd64", tag("cp27", "cp27m", "macox_10_10_intel")},

		{"windows", "386", tag("cp27", "cp27m", "win32")},
		{"windows", "amd64", tag("cp27", "cp27m", "win_amd64")},
	}

	// Run verification within the scope of a tempdir. We use an explicit tempdir
	// for caching so our verification resolves everything against the live CIPD
	// service. We will, however, share a cache directory and root in between
	// verification rounds so that we can cache duplicate lookups.
	td := filesystem.TempDir{
		Prefix: "vpython_verification",
	}
	_ = td.With(func(tdir string) error {
		// Clone our default package loader and configure it for verification.
		plBase := cipdPackageLoader
		plBase.Options.CacheDir = filepath.Join(tdir, "cache")
		plBase.Options.Root = filepath.Join(tdir, "root")

		for _, vs := range scenarios {
			// Can stop generating early if our Context is cancelled.
			select {
			case <-c.Done():
				return c.Err()
			default:
			}

			// Clone our base package loader for verification. Override CIPD template
			// parameters for this verification scenario.
			pl := plBase
			pl.Template = vs.wrapTemplateFunc(pl.Template)

			vf(c, vs.title(), &pl, vs.environment())
		}

		return nil
	})
}

type verificationScenario struct {
	os   string
	arch string
	tag  *vpython.Environment_Pep425Tag
}

func (vs *verificationScenario) title() string {
	return fmt.Sprintf("platform=%s,pep425=%s", vs.platform(), vs.tag.TagString())
}

func (vs *verificationScenario) platform() string { return fmt.Sprintf("%s-%s", vs.os, vs.arch) }

func (vs *verificationScenario) wrapTemplateFunc(base cipd.TemplateFunc) cipd.TemplateFunc {
	return func(c context.Context, e *vpython.Environment) (map[string]string, error) {
		v, err := base(c, e)
		if err != nil {
			return nil, err
		}

		if v == nil {
			v = make(map[string]string, 3)
		}
		v["os"] = vs.os
		v["arch"] = vs.arch
		v["platform"] = vs.platform()
		return v, nil
	}
}

func (vs *verificationScenario) environment() *vpython.Environment {
	return &vpython.Environment{
		Pep425Tag: []*vpython.Environment_Pep425Tag{vs.tag},
	}
}
