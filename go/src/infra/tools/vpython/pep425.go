// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"strconv"
	"strings"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/vpython/api/vpython"
	"github.com/luci/luci-go/vpython/cipd"
)

// pep425MacArch is a parsed PEP425 Mac architecture string.
//
// The string is formatted:
// macosx_<maj>_<min>_<cpu-arch>
//
// For example:
//	- macosx_10_6_intel
//	- macosx_10_0_fat
//	- macosx_10_2_x86_64
type pep425MacArch struct {
	major int
	minor int
	arch  string
}

// parsePEP425MacArch parses a pep425MacArch from the supplied architecture
// string. If the string does not contain a recognizable Mac architecture, this
// function returns nil.
func parsePEP425MacArch(v string) *pep425MacArch {
	parts := strings.SplitN(v, "_", 4)
	if len(parts) != 4 {
		return nil
	}
	if parts[0] != "macosx" {
		return nil
	}

	var ma pep425MacArch
	var err error
	if ma.major, err = strconv.Atoi(parts[1]); err != nil {
		return nil
	}
	if ma.minor, err = strconv.Atoi(parts[2]); err != nil {
		return nil
	}

	ma.arch = parts[3]
	return &ma
}

// less returns true if "ma" represents a Mac version before "other".
func (ma *pep425MacArch) less(other *pep425MacArch) bool {
	switch {
	case ma.major < other.major:
		return true
	case other.major > ma.major:
		return false
	case ma.minor < other.minor:
		return true
	default:
		return false
	}
}

// pep425IsBetterMacArch processes two PEP425 architecture strings and returns
// true if "candidate" is a superior PEP425 tag candidate than "cur".
//
// This function favors, in order:
//	- Mac architectures over non-Mac architectures,
//	- "intel" package builds over non-"intel"
//	- Older Mac versions over newer ones
func pep425IsBetterMacArch(cur, candidate string) bool {
	// Parse a Mac architecture string
	curArch := parsePEP425MacArch(cur)
	candidateArch := parsePEP425MacArch(candidate)
	switch {
	case curArch == nil:
		return candidateArch != nil
	case candidateArch == nil:
		return false
	case curArch.arch != "intel" && candidateArch.arch == "intel":
		// Prefer "intel" architecture over others, since it's more modern and
		// generic.
		return true
	case curArch.arch == "intel" && candidateArch.arch != "intel":
		return false
	case candidateArch.less(curArch):
		// We prefer the lowest Mac architecture available.
		return true
	default:
		return false
	}
}

// pep425IsBetterLinuxArch processes two PEP425 architecture strings and returns
// true if "candidate" is a superior PEP425 tag candidate than "cur".
//
// This function favors, in order:
//	- Linux architectures over non-Linux architectures.
//	- "manylinux1_" over non-"manylinux1_".
//
// Examples of expected Linux architecture strings are:
//	- linux1_x86_64
//	- linux1_i686
//	- manylinux1_i686
func pep425IsBetterLinuxArch(cur, candidate string) bool {
	// Determies if the specified architecture is a Linux architecture and, if so,
	// is it a "manylinux1_" Linux architecture.
	isLinuxArch := func(arch string) (is bool, many bool) {
		switch {
		case strings.HasPrefix(arch, "linux_"):
			is = true
		case strings.HasPrefix(arch, "manylinux1_"):
			is, many = true, true
		}
		return
	}

	// We prefer "manylinux1_" architectures over "linux_" architectures.
	curIs, curMany := isLinuxArch(cur)
	candidateIs, candidateMany := isLinuxArch(candidate)
	switch {
	case !curIs:
		return candidateIs
	case !candidateIs:
		return false
	case curMany:
		return false
	default:
		return candidateMany
	}
}

// pep425TagSelector chooses the "best" PEP425 tag from a set of potential tags.
// This "best" tag will be used to resolve our CIPD templates and allow for
// Python implementation-specific CIPD template parameters.
func pep425TagSelector(goOS string, tags []*vpython.Pep425Tag) *vpython.Pep425Tag {
	var best *vpython.Pep425Tag

	// isPreferredOSArch is an OS-specific architecture preference function.
	isPreferredOSArch := func(cur, candidate string) bool { return false }
	switch goOS {
	case "linux":
		isPreferredOSArch = pep425IsBetterLinuxArch
	case "darwin":
		isPreferredOSArch = pep425IsBetterMacArch
	}

	isBetter := func(t *vpython.Pep425Tag) bool {
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
		case isPreferredOSArch(best.Arch, t.Arch):
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

// getPEP425CIPDTemplates returns the set of CIPD template strings for a
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
//
// This function also backports the Python platform into the CIPD "platform"
// field, ensuring that regardless of the host architecture, the Python CIPD
// wheel is chosen based solely on that host's Python interpreter.
//
// Infra CIPD packages tend to use "${platform}" (generic) combined with
// "${py_abi}" and "${py_arch}" to identify its packages.
func getPEP425CIPDTemplateForTag(tag *vpython.Pep425Tag) (map[string]string, error) {
	if tag == nil {
		return nil, errors.New("no PEP425 tag")
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

	// Override the CIPD "platform" based on the PEP425 tag. This allows selection
	// of Python wheels based on the architecture of the Python executable rather
	// than the architecture of the underlying platform.
	//
	// For example, a 64-bit Windows version can run 32-bit Python, and we'll
	// want to use 32-bit Python wheels.
	platform := cipd.PlatformForPEP425Tag(tag)
	if platform == "" {
		return nil, errors.Reason("failed to infer CIPD platform for tag [%(tag)s]").
			D("tag", tag.TagString()).
			Err()
	}
	template["platform"] = platform

	return template, nil
}
