// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/errors"
)

func installPackages(ctx context.Context, xcodeVersion, xcodeAppPath, cipdPackagePrefix string, kind KindType) error {
	cipdArgs := []string{
		"ensure", "-ensure-file", "-",
		"-root", xcodeAppPath,
	}
	ensureSpec := cipdPackagePrefix + "/mac " + xcodeVersion + "\n"
	if kind == iosKind {
		ensureSpec += cipdPackagePrefix + "/ios " + xcodeVersion + "\n"
	}
	if err := RunWithStdin(ctx, ensureSpec, "cipd", cipdArgs...); err != nil {
		return errors.Annotate(err, "failed to install CIPD packages: %s", ensureSpec).Err()
	}
	return nil
}

func needToAcceptLicense(ctx context.Context, xcodeAppPath, acceptedLicensesFile string) bool {
	licenseInfoFile := filepath.Join(xcodeAppPath, "Contents", "Resources", "LicenseInfo.plist")

	licenseID, licenseType, err := getXcodeLicenseInfo(licenseInfoFile)
	if err != nil {
		errors.Log(ctx, err)
		return true
	}

	acceptedLicenseID, err := getXcodeAcceptedLicense(acceptedLicensesFile, licenseType)
	if err != nil {
		errors.Log(ctx, err)
		return true
	}

	// Historically all Xcode build numbers have been in the format of AANNNN, so
	// a simple string compare works.  If Xcode's build numbers change this may
	// need a more complex compare.
	if licenseID <= acceptedLicenseID {
		// Don't accept the license of older toolchain builds, this will break the
		// license of newer builds.
		return false
	}
	return true
}

func getXcodePath(ctx context.Context) string {
	path, err := RunOutput(ctx, "sudo", "/usr/bin/xcode-select", "-p")
	if err != nil {
		return ""
	}
	return strings.Trim(path, " \n")
}

func setXcodePath(ctx context.Context, xcodeAppPath string) error {
	err := RunCommand(ctx, "sudo", "/usr/bin/xcode-select", "-s", xcodeAppPath)
	if err != nil {
		return errors.Annotate(err, "failed xcode-select -s %s", xcodeAppPath).Err()
	}
	return nil
}

func acceptLicense(ctx context.Context, xcodeAppPath string) error {
	err := RunCommand(ctx, "sudo", "/usr/bin/xcodebuild", "-license", "accept")
	if err != nil {
		return errors.Annotate(err, "failed to accept new license").Err()
	}
	return nil
}

func finalizeInstall(ctx context.Context, xcodeAppPath string) error {
	err := RunCommand(ctx, "sudo", "/usr/bin/xcodebuild", "-runFirstLaunch")
	if err != nil {
		return errors.Annotate(err, "failed to install Xcode packages").Err()
	}
	return nil
}

// Plan:
// - Install the required set of CIPD packages in the <outputDir>/Xcode.app
// - Check the build type (GM or Beta) and license ID of the installed Xcode,
//   compared with the system's accepted license in
//   /Library/Preferences/com.apple.dt.Xcode.plist
// - If needed, accept the license and install the packages (xcodebuild -runFirstLaunch)

func installXcode(ctx context.Context,
	xcodeVersion, xcodeAppPath, acceptedLicensesFile, cipdPackagePrefix string,
	kind KindType) error {
	if err := os.MkdirAll(xcodeAppPath, 0700); err != nil {
		return errors.Annotate(err, "failed to create a folder %s", xcodeAppPath).Err()
	}
	if err := installPackages(ctx, xcodeVersion, xcodeAppPath, cipdPackagePrefix, kind); err != nil {
		return err
	}
	if needToAcceptLicense(ctx, xcodeAppPath, acceptedLicensesFile) {
		oldPath := getXcodePath(ctx)
		if oldPath != "" {
			defer setXcodePath(ctx, oldPath)
		}
		if err := setXcodePath(ctx, xcodeAppPath); err != nil {
			return err
		}
		if err := acceptLicense(ctx, xcodeAppPath); err != nil {
			return err
		}
		if err := finalizeInstall(ctx, xcodeAppPath); err != nil {
			return err
		}
	}
	return nil
}
