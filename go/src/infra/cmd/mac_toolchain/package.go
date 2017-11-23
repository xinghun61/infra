// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/net/context"
	"gopkg.in/yaml.v2"

	cipd "go.chromium.org/luci/cipd/client/cipd/local"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
)

// defaultExcludePrefixes excludes parts of Xcode.app that are not necessary for
// any of our purposes. Specifically, it excludes unused platforms like
// AppleTVOS and WatchOS, documentation, and anything related to Swift.
var defaultExcludePrefixes = []string{
	"Contents/Applications",
	"Contents/Developer/Platforms/AppleTVOS.platform",
	"Contents/Developer/Platforms/AppleTVSimulator.platform",
	"Contents/Developer/Platforms/WatchOS.platform",
	"Contents/Developer/Platforms/WatchSimulator.platform",
	// Excludes both .../swift/ and .../swift_static/.
	"Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/swift",
}

// macExcludePrefixes excludes parts of Xcode.app not required for building
// Chrome on Mac OS.
var macExcludePrefixes = []string{
	"Contents/Developer/Platforms/iPhoneOS.platform/Developer/Library/CoreSimulator",
}

// Packages is the set of CIPD package definitions. The key is a convenience
// package name for direct reference.
type Packages map[string]cipd.PackageDef

// PackageSpec bundles the package name with a path to its YAML definition file.
type PackageSpec struct {
	Name     string
	YamlPath string
}

func isExcluded(path string, prefixes []string) bool {
	for _, prefix := range prefixes {
		p := filepath.Join(strings.Split(prefix, "/")...)
		if strings.HasPrefix(path, p) {
			return true
		}
	}
	return false
}

func makePackages(xcodeAppPath string, cipdPackagePrefix string, excludeAll, excludeMac []string) (p Packages, err error) {
	absXcodeAppPath, err := filepath.Abs(xcodeAppPath)
	if err != nil {
		err = errors.Annotate(err, "failed to create an absolute path from %s", xcodeAppPath).Err()
		return
	}
	packageDef := cipd.PackageDef{
		Root:        absXcodeAppPath,
		InstallMode: "copy",
	}
	mac := packageDef
	mac.Package = cipdPackagePrefix + "/mac"
	mac.Data = []cipd.PackageChunkDef{
		{VersionFile: ".xcode_versions/mac.cipd_version"},
	}

	ios := packageDef
	ios.Package = cipdPackagePrefix + "/ios"
	ios.Data = []cipd.PackageChunkDef{
		{VersionFile: ".xcode_versions/ios.cipd_version"},
	}

	err = filepath.Walk(absXcodeAppPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.Mode().IsDir() {
			if !strings.HasPrefix(path, absXcodeAppPath+string(os.PathSeparator)) {
				return errors.Reason("file is not in the source folder: %s", path).Err()
			}
			relPath := path[len(absXcodeAppPath)+1:]
			if isExcluded(relPath, excludeAll) {
				return nil
			}
			if isExcluded(relPath, excludeMac) {
				ios.Data = append(ios.Data, cipd.PackageChunkDef{File: relPath})
			} else {
				mac.Data = append(mac.Data, cipd.PackageChunkDef{File: relPath})
			}
		}
		return nil
	})
	p = Packages{"mac": mac, "ios": ios}
	return
}

// buildCipdPackages builds and optionally uploads CIPD packages to the
// server. `buildFn` callback takes a PackageSpec for each package in `packages`
// and is expected to call `cipd pkg-build` or `cipd create` on it.
func buildCipdPackages(packages Packages, buildFn func(PackageSpec) error) error {
	tmpDir, err := ioutil.TempDir("", "mac_toolchain_")
	if err != nil {
		return errors.Annotate(err, "cannot create a temporary folder for CIPD package configuration files in %s", os.TempDir()).Err()
	}
	defer os.RemoveAll(tmpDir)

	// Iterate deterministically (for testability).
	names := make([]string, 0, len(packages))
	for name := range packages {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		p := packages[name]
		yamlBytes, err := yaml.Marshal(p)
		if err != nil {
			return errors.Annotate(err, "failed to serialize %s.yaml", name).Err()
		}
		yamlPath := filepath.Join(tmpDir, name+".yaml")
		if err = ioutil.WriteFile(yamlPath, yamlBytes, 0600); err != nil {
			return errors.Annotate(err, "failed to write package definition file %s", yamlPath).Err()
		}
		if err = buildFn(PackageSpec{Name: p.Package, YamlPath: yamlPath}); err != nil {
			return err
		}
	}
	return nil
}

func createBuilder(ctx context.Context, xcodeVersion, buildVersion, serviceAccountJSON, outputDir string) func(PackageSpec) error {
	builder := func(p PackageSpec) error {
		args := []string{}
		if outputDir != "" {
			pkgParts := strings.Split(p.Name, "/")
			fileName := pkgParts[len(pkgParts)-1] + ".cipd"
			args = append(args, "pkg-build",
				"-out", filepath.Join(outputDir, fileName),
			)
			// Ensure outputDir exists. MkdirAll returns nil if path already exists.
			if err := os.MkdirAll(outputDir, 0777); err != nil {
				return errors.Annotate(err, "failed to create output directory %s", outputDir).Err()
			}
		} else {
			args = append(args,
				"create", "-verification-timeout", "60m",
				"-tag", "xcode_version:"+xcodeVersion,
				"-tag", "build_version:"+buildVersion,
				"-ref", strings.ToLower(buildVersion), // Refs must match [a-z0-9_-]*
				"-ref", "latest",
			)
		}
		args = append(args, "-pkg-def", p.YamlPath)
		if serviceAccountJSON != "" {
			args = append(args, "-service-account-json", serviceAccountJSON)
		}

		logging.Infof(ctx, "Creating a CIPD package %s", p.Name)
		logging.Debugf(ctx, "Running cipd %s", strings.Join(args, " "))
		if err := RunCommand(ctx, "cipd", args...); err != nil {
			return errors.Annotate(err, "creating a CIPD package failed.").Err()
		}
		return nil
	}
	return builder
}

func packageXcode(ctx context.Context, xcodeAppPath string, cipdPackagePrefix, serviceAccountJSON, outputDir string) error {
	xcodeVersion, buildVersion, err := getXcodeVersion(filepath.Join(xcodeAppPath, "Contents", "version.plist"))
	if err != nil {
		return errors.Annotate(err, "this doesn't look like a valid Xcode.app folder: %s", xcodeAppPath).Err()
	}

	packages, err := makePackages(xcodeAppPath, cipdPackagePrefix,
		defaultExcludePrefixes, macExcludePrefixes)
	if err != nil {
		return err
	}

	buildFn := createBuilder(ctx, xcodeVersion, buildVersion, serviceAccountJSON, outputDir)

	if err = buildCipdPackages(packages, buildFn); err != nil {
		return err
	}

	fmt.Printf("\nCIPD packages:\n")
	for _, p := range packages {
		fmt.Printf("  %s  %s\n", p.Package, strings.ToLower(buildVersion))
	}

	return nil
}
