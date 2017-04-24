// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"strings"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/vpython/api/vpython"
)

// pep425TagSelector chooses the "best" PEP425 tag from a set of potential tags.
// This "best" tag will be used to resolve our CIPD templates and allow for
// Python implementation-specific CIPD template parameters.
func pep425TagSelector(tags []*vpython.Environment_Pep425Tag) *vpython.Environment_Pep425Tag {
	var best *vpython.Environment_Pep425Tag
	isBetter := func(t *vpython.Environment_Pep425Tag) bool {
		switch {
		case best == nil:
			return true
		case t.Count() > best.Count():
			// More populated fields is more specificity.
			return true
		case best.AnyArch() && !t.AnyArch():
			// More specific architecture is preferred.
			return true
		case !best.HasABI() && t.HasABI():
			// More specific ABI is preferred.
			return true
		case strings.HasPrefix(best.Arch, "linux_") && strings.HasPrefix(t.Arch, "manylinux1_"):
			// Linux: Prefer "manylinux_" to "linux_".
			return true
		case strings.HasPrefix(best.Version, "py") && !strings.HasPrefix(t.Version, "py"):
			// Prefer specific Python (e.g., cp27) version over generic (e.g., py27).
			return true

		default:
			return false
		}
	}

	for _, t := range tags {
		if isBetter(t) {
			best = t
		}
	}
	return best
}

// getCIPDTemplatesForEnvironment returns the set of CIPD template strings for a
// given PEP425 tag.
//
// Template parameters are derived from the most representative PEP425 tag.
// Any missing tag parameters will result in their associated template
// parameters not getting exported.
//
// The full set of exported tag parameters is:
// - py_version: The PEP425 Python "version" (e.g., "cp27").
// - py_abi: The PEP425 Python ABI (e.g., "cp27mu").
// - py_arch: The PEP425 Python architecture (e.g., "manylinux1_x86_64").
// - py_tag: The full PEP425 tag (e.g., "cp27-cp27mu-manylinux1_x86_64").
func getCIPDTemplatesForEnvironment(c context.Context, e *vpython.Environment) (map[string]string, error) {
	tag := pep425TagSelector(e.Pep425Tag)
	if tag == nil {
		return nil, nil
	}

	template := make(map[string]string, 4)
	if tag.Version != "" {
		template["py_version"] = tag.Version
	}
	if tag.Abi != "" {
		template["py_abi"] = tag.Abi
	}
	if tag.Arch != "" {
		template["py_arch"] = tag.Arch
	}
	if tag.Version != "" && tag.Abi != "" && tag.Arch != "" {
		template["py_tag"] = tag.TagString()
	}
	return template, nil
}
