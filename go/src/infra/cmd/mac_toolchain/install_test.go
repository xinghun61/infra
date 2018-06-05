// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"path/filepath"
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/errors"

	. "github.com/smartystreets/goconvey/convey"
)

func TestInstallXcode(t *testing.T) {
	t.Parallel()

	Convey("installXcode works", t, func() {
		var s MockSession
		ctx := useMockCmd(context.Background(), &s)
		installArgs := InstallArgs{
			xcodeVersion:           "testVersion",
			xcodeAppPath:           "testdata/Xcode-old.app",
			acceptedLicensesFile:   "testdata/acceptedLicenses.plist",
			cipdPackagePrefix:      "test/prefix",
			kind:                   macKind,
			serviceAccountJSON:     "",
			packageInstallerOnBots: "testdata/dummy_installer",
		}

		Convey("for accepted license, mac", func() {
			err := installXcode(ctx, installArgs)
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 6)
			So(s.Calls[0].Executable, ShouldEqual, "cipd")
			So(s.Calls[0].Args, ShouldResemble, []string{
				"puppet-check-updates", "-ensure-file", "-", "-root", "testdata/Xcode-old.app",
			})
			So(s.Calls[0].ConsumedStdin, ShouldEqual, "test/prefix/mac testVersion\n")

			So(s.Calls[1].Executable, ShouldEqual, "cipd")
			So(s.Calls[1].Args, ShouldResemble, []string{
				"ensure", "-ensure-file", "-", "-root", "testdata/Xcode-old.app",
			})
			So(s.Calls[1].ConsumedStdin, ShouldEqual, "test/prefix/mac testVersion\n")

			So(s.Calls[2].Executable, ShouldEqual, "chmod")
			So(s.Calls[2].Args, ShouldResemble, []string{
				"-R", "u+w", "testdata/Xcode-old.app",
			})

			So(s.Calls[3].Executable, ShouldEqual, "/usr/bin/xcodebuild")
			So(s.Calls[3].Args, ShouldResemble, []string{"-checkFirstLaunchStatus"})

			So(s.Calls[4].Executable, ShouldEqual, "/usr/sbin/DevToolsSecurity")
			So(s.Calls[4].Args, ShouldResemble, []string{"-status"})

			So(s.Calls[5].Executable, ShouldEqual, "sudo")
			So(s.Calls[5].Args, ShouldResemble, []string{
				"/usr/sbin/DevToolsSecurity",
				"-enable",
			})
		})

		Convey("for already installed package with Developer mode enabled and -runFirstLaunch needs to run", func() {
			s.ReturnError = []error{
				errors.Reason("CIPD package already installed").Err(),
				errors.Reason("Need -runFirstLaunch").Err(),
			}
			s.ReturnOutput = []string{
				"",
				"Developer mode is currently enabled.\n",
			}
			err := installXcode(ctx, installArgs)
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 5)
			So(s.Calls[0].Executable, ShouldEqual, "cipd")
			So(s.Calls[0].Args, ShouldResemble, []string{
				"puppet-check-updates", "-ensure-file", "-", "-root", "testdata/Xcode-old.app",
			})
			So(s.Calls[0].ConsumedStdin, ShouldEqual, "test/prefix/mac testVersion\n")

			So(s.Calls[1].Executable, ShouldEqual, "/usr/bin/xcodebuild")
			So(s.Calls[1].Args, ShouldResemble, []string{"-checkFirstLaunchStatus"})

			So(s.Calls[2].Executable, ShouldEqual, "sudo")
			So(s.Calls[2].Args, ShouldResemble, []string{"/usr/bin/xcodebuild", "-runFirstLaunch"})

			So(s.Calls[3].Executable, ShouldEqual, "/usr/sbin/DevToolsSecurity")
			So(s.Calls[3].Args, ShouldResemble, []string{"-status"})
		})

		Convey("for already installed package with Developer mode disabled", func() {
			s.ReturnError = []error{errors.Reason("already installed").Err()}
			s.ReturnOutput = []string{
				"",
				"Developer mode is currently disabled.",
			}
			err := installXcode(ctx, installArgs)
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 4)
			So(s.Calls[0].Executable, ShouldEqual, "cipd")
			So(s.Calls[0].Args, ShouldResemble, []string{
				"puppet-check-updates", "-ensure-file", "-", "-root", "testdata/Xcode-old.app",
			})
			So(s.Calls[0].ConsumedStdin, ShouldEqual, "test/prefix/mac testVersion\n")

			So(s.Calls[1].Executable, ShouldEqual, "/usr/bin/xcodebuild")
			So(s.Calls[1].Args, ShouldResemble, []string{"-checkFirstLaunchStatus"})

			So(s.Calls[2].Executable, ShouldEqual, "/usr/sbin/DevToolsSecurity")
			So(s.Calls[2].Args, ShouldResemble, []string{"-status"})

			So(s.Calls[3].Executable, ShouldEqual, "sudo")
			So(s.Calls[3].Args, ShouldResemble, []string{
				"/usr/sbin/DevToolsSecurity",
				"-enable",
			})
		})

		Convey("with a service account", func() {
			installArgs.serviceAccountJSON = "test/service-account.json"
			err := installXcode(ctx, installArgs)
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 6)
			So(s.Calls[0].Executable, ShouldEqual, "cipd")
			So(s.Calls[0].Args, ShouldResemble, []string{
				"puppet-check-updates", "-ensure-file", "-", "-root", "testdata/Xcode-old.app",
				"-service-account-json", "test/service-account.json",
			})
			So(s.Calls[0].ConsumedStdin, ShouldEqual, "test/prefix/mac testVersion\n")

			So(s.Calls[1].Executable, ShouldEqual, "cipd")
			So(s.Calls[1].Args, ShouldResemble, []string{
				"ensure", "-ensure-file", "-", "-root", "testdata/Xcode-old.app",
				"-service-account-json", "test/service-account.json",
			})
			So(s.Calls[1].ConsumedStdin, ShouldEqual, "test/prefix/mac testVersion\n")

			So(s.Calls[2].Executable, ShouldEqual, "chmod")
			So(s.Calls[2].Args, ShouldResemble, []string{
				"-R", "u+w", "testdata/Xcode-old.app",
			})

			So(s.Calls[3].Executable, ShouldEqual, "/usr/bin/xcodebuild")
			So(s.Calls[3].Args, ShouldResemble, []string{"-checkFirstLaunchStatus"})

			So(s.Calls[4].Executable, ShouldEqual, "/usr/sbin/DevToolsSecurity")
			So(s.Calls[4].Args, ShouldResemble, []string{"-status"})

			So(s.Calls[5].Executable, ShouldEqual, "sudo")
			So(s.Calls[5].Args, ShouldResemble, []string{"/usr/sbin/DevToolsSecurity", "-enable"})
		})

		Convey("for new license, ios", func() {
			s.ReturnError = []error{errors.Reason("already installed").Err()}
			s.ReturnOutput = []string{
				"",
				"old/xcode/path",
				"Developer mode is currently disabled.",
			}

			installArgs.xcodeAppPath = "testdata/Xcode-new.app"
			installArgs.kind = iosKind
			err := installXcode(ctx, installArgs)
			So(err, ShouldBeNil)
			So(len(s.Calls), ShouldEqual, 8)

			So(s.Calls[0].Executable, ShouldEqual, "cipd")
			So(s.Calls[0].Args, ShouldResemble, []string{
				"puppet-check-updates", "-ensure-file", "-", "-root", "testdata/Xcode-new.app",
			})
			So(s.Calls[0].ConsumedStdin, ShouldEqual,
				"test/prefix/mac testVersion\n"+
					"test/prefix/ios testVersion\n")

			So(s.Calls[1].Executable, ShouldEqual, "/usr/bin/xcode-select")
			So(s.Calls[1].Args, ShouldResemble, []string{"-p"})

			So(s.Calls[2].Executable, ShouldEqual, "sudo")
			So(s.Calls[2].Args, ShouldResemble, []string{"/usr/bin/xcode-select", "-s", "testdata/Xcode-new.app"})

			So(s.Calls[3].Executable, ShouldEqual, "sudo")
			So(s.Calls[3].Args, ShouldResemble, []string{"/usr/bin/xcodebuild", "-license", "accept"})

			So(s.Calls[4].Executable, ShouldEqual, "/usr/bin/xcodebuild")
			So(s.Calls[4].Args, ShouldResemble, []string{"-checkFirstLaunchStatus"})

			So(s.Calls[5].Executable, ShouldEqual, "/usr/sbin/DevToolsSecurity")
			So(s.Calls[5].Args, ShouldResemble, []string{"-status"})

			So(s.Calls[6].Executable, ShouldEqual, "sudo")
			So(s.Calls[6].Args, ShouldResemble, []string{"/usr/sbin/DevToolsSecurity", "-enable"})

			So(s.Calls[7].Executable, ShouldEqual, "sudo")
			So(s.Calls[7].Args, ShouldResemble, []string{"/usr/bin/xcode-select", "-s", "old/xcode/path"})

		})

		Convey("for legacy Xcode version on a mac bot", func() {
			s.ReturnError = []error{errors.Reason("already installed").Err()}
			s.ReturnOutput = []string{"", "old/xcode/path"}

			installArgs.xcodeAppPath = "testdata/Xcode-legacy.app"
			installArgs.xcodeVersion = "8e3004b"
			err := installXcode(ctx, installArgs)
			So(err, ShouldBeNil)
			So(len(s.Calls), ShouldEqual, 10)

			So(s.Calls[0].Executable, ShouldEqual, "cipd")
			So(s.Calls[0].Args, ShouldResemble, []string{
				"puppet-check-updates", "-ensure-file", "-", "-root", "testdata/Xcode-legacy.app",
			})
			So(s.Calls[0].ConsumedStdin, ShouldEqual, "test/prefix/mac 8e3004b\n")

			So(s.Calls[1].Executable, ShouldEqual, "/usr/bin/xcode-select")
			So(s.Calls[1].Args, ShouldResemble, []string{"-p"})

			So(s.Calls[2].Executable, ShouldEqual, "sudo")
			So(s.Calls[2].Args, ShouldResemble, []string{"/usr/bin/xcode-select", "-s", "testdata/Xcode-legacy.app"})

			So(s.Calls[3].Executable, ShouldEqual, "sudo")
			So(s.Calls[3].Args, ShouldResemble, []string{"/usr/bin/xcodebuild", "-license", "accept"})

			So(s.Calls[4].Executable, ShouldEqual, "sudo")
			So(s.Calls[4].Args, ShouldResemble, []string{
				"testdata/dummy_installer", "--package-path",
				filepath.Join("testdata", "Xcode-legacy.app", "Contents", "Resources", "Packages", "MobileDevice.pkg"),
			})

			So(s.Calls[5].Executable, ShouldEqual, "sudo")
			So(s.Calls[5].Args, ShouldResemble, []string{
				"testdata/dummy_installer", "--package-path",
				filepath.Join("testdata", "Xcode-legacy.app", "Contents", "Resources", "Packages", "MobileDeviceDevelopment.pkg"),
			})

			So(s.Calls[6].Executable, ShouldEqual, "sudo")
			So(s.Calls[6].Args, ShouldResemble, []string{
				"testdata/dummy_installer", "--package-path",
				filepath.Join("testdata", "Xcode-legacy.app", "Contents", "Resources", "Packages", "XcodeSystemResources.pkg"),
			})

			So(s.Calls[7].Executable, ShouldEqual, "/usr/sbin/DevToolsSecurity")
			So(s.Calls[7].Args, ShouldResemble, []string{"-status"})

			So(s.Calls[8].Executable, ShouldEqual, "sudo")
			So(s.Calls[8].Args, ShouldResemble, []string{"/usr/sbin/DevToolsSecurity", "-enable"})

			So(s.Calls[9].Executable, ShouldEqual, "sudo")
			So(s.Calls[9].Args, ShouldResemble, []string{"/usr/bin/xcode-select", "-s", "old/xcode/path"})

		})

		Convey("for legacy Xcode version on a dev machine", func() {
			s.ReturnError = []error{errors.Reason("already installed").Err()}
			s.ReturnOutput = []string{"", "old/xcode/path"}

			installArgs.xcodeAppPath = "testdata/Xcode-legacy.app"
			installArgs.xcodeVersion = "8e3004b"
			installArgs.packageInstallerOnBots = "nonexistent"
			err := installXcode(ctx, installArgs)
			So(err, ShouldBeNil)
			So(len(s.Calls), ShouldEqual, 10)

			So(s.Calls[0].Executable, ShouldEqual, "cipd")
			So(s.Calls[0].Args, ShouldResemble, []string{
				"puppet-check-updates", "-ensure-file", "-", "-root", "testdata/Xcode-legacy.app",
			})
			So(s.Calls[0].ConsumedStdin, ShouldEqual, "test/prefix/mac 8e3004b\n")

			So(s.Calls[1].Executable, ShouldEqual, "/usr/bin/xcode-select")
			So(s.Calls[1].Args, ShouldResemble, []string{"-p"})

			So(s.Calls[2].Executable, ShouldEqual, "sudo")
			So(s.Calls[2].Args, ShouldResemble, []string{"/usr/bin/xcode-select", "-s", "testdata/Xcode-legacy.app"})

			So(s.Calls[3].Executable, ShouldEqual, "sudo")
			So(s.Calls[3].Args, ShouldResemble, []string{"/usr/bin/xcodebuild", "-license", "accept"})

			So(s.Calls[4].Executable, ShouldEqual, "sudo")
			So(s.Calls[4].Args, ShouldResemble, []string{
				"installer", "-package",
				filepath.Join("testdata", "Xcode-legacy.app", "Contents", "Resources", "Packages", "MobileDevice.pkg"),
				"-target", "/",
			})

			So(s.Calls[5].Executable, ShouldEqual, "sudo")
			So(s.Calls[5].Args, ShouldResemble, []string{
				"installer", "-package",
				filepath.Join("testdata", "Xcode-legacy.app", "Contents", "Resources", "Packages", "MobileDeviceDevelopment.pkg"),
				"-target", "/",
			})

			So(s.Calls[6].Executable, ShouldEqual, "sudo")
			So(s.Calls[6].Args, ShouldResemble, []string{
				"installer", "-package",
				filepath.Join("testdata", "Xcode-legacy.app", "Contents", "Resources", "Packages", "XcodeSystemResources.pkg"),
				"-target", "/",
			})

			So(s.Calls[7].Executable, ShouldEqual, "/usr/sbin/DevToolsSecurity")
			So(s.Calls[7].Args, ShouldResemble, []string{"-status"})

			So(s.Calls[8].Executable, ShouldEqual, "sudo")
			So(s.Calls[8].Args, ShouldResemble, []string{"/usr/sbin/DevToolsSecurity", "-enable"})

			So(s.Calls[9].Executable, ShouldEqual, "sudo")
			So(s.Calls[9].Args, ShouldResemble, []string{"/usr/bin/xcode-select", "-s", "old/xcode/path"})

		})
	})
}
