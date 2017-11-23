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

func installPackages(ctx context.Context, xcodeVersion, xcodeAppPath, cipdPackagePrefix string, kind KindType, serviceAccountJSON string) error {
	cipdArgs := []string{
		"-ensure-file", "-",
		"-root", xcodeAppPath,
	}
	if serviceAccountJSON != "" {
		cipdArgs = append(cipdArgs, "-service-account-json", serviceAccountJSON)
	}
	cipdCheckArgs := append([]string{"puppet-check-updates"}, cipdArgs...)
	cipdEnsureArgs := append([]string{"ensure"}, cipdArgs...)
	ensureSpec := cipdPackagePrefix + "/mac " + xcodeVersion + "\n"
	if kind == iosKind {
		ensureSpec += cipdPackagePrefix + "/ios " + xcodeVersion + "\n"
	}
	// Check if `cipd ensure` will do something. Note: `cipd puppet-check-updates`
	// returns code 0 when `cipd ensure` has work to do, and "fails" otherwise.
	// TODO(sergeyberezin): replace this with a better option when
	// https://crbug.com/788032 is fixed.
	if err := RunWithStdin(ctx, ensureSpec, "cipd", cipdCheckArgs...); err != nil {
		return nil
	}

	if err := RunWithStdin(ctx, ensureSpec, "cipd", cipdEnsureArgs...); err != nil {
		return errors.Annotate(err, "failed to install CIPD packages: %s", ensureSpec).Err()
	}
	// Xcode really wants its files to be user-writable (hangs mysteriously
	// otherwise). CIPD by default installs everything read-only. Update
	// permissions post-install.
	if err := RunCommand(ctx, "chmod", "-R", "u+w", xcodeAppPath); err != nil {
		return errors.Annotate(err, "failed to update Xcode.app permissions in %s", xcodeAppPath).Err()
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

func installXcode(ctx context.Context,
	xcodeVersion, xcodeAppPath, acceptedLicensesFile, cipdPackagePrefix string,
	kind KindType, serviceAccountJSON string) error {
	if err := os.MkdirAll(xcodeAppPath, 0700); err != nil {
		return errors.Annotate(err, "failed to create a folder %s", xcodeAppPath).Err()
	}
	if err := installPackages(ctx, xcodeVersion, xcodeAppPath, cipdPackagePrefix, kind, serviceAccountJSON); err != nil {
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
