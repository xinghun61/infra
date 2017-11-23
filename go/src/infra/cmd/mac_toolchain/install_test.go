// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
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

		Convey("for accepted license, mac", func() {
			err := installXcode(ctx, "testVersion", "testdata/Xcode-old.app",
				"testdata/acceptedLicenses.plist", "test/prefix", macKind, "")
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 3)
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
		})

		Convey("for already installed package", func() {
			s.ReturnError = []error{errors.Reason("already installed").Err()}
			err := installXcode(ctx, "testVersion", "testdata/Xcode-old.app",
				"testdata/acceptedLicenses.plist", "test/prefix", macKind, "")
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 1)
			So(s.Calls[0].Executable, ShouldEqual, "cipd")
			So(s.Calls[0].Args, ShouldResemble, []string{
				"puppet-check-updates", "-ensure-file", "-", "-root", "testdata/Xcode-old.app",
			})
			So(s.Calls[0].ConsumedStdin, ShouldEqual, "test/prefix/mac testVersion\n")
		})

		Convey("with a service account", func() {
			err := installXcode(ctx, "testVersion", "testdata/Xcode-old.app",
				"testdata/acceptedLicenses.plist", "test/prefix", macKind, "test/service-account.json")
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 3)
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
		})

		Convey("for new license, ios", func() {
			s.ReturnError = []error{errors.Reason("already installed").Err()}
			s.ReturnOutput = []string{"", "old/xcode/path"}
			err := installXcode(ctx, "testVersion", "testdata/Xcode-new.app",
				"testdata/acceptedLicenses.plist", "test/prefix", iosKind, "")
			So(err, ShouldBeNil)
			So(len(s.Calls), ShouldEqual, 6)

			So(s.Calls[0].Executable, ShouldEqual, "cipd")
			So(s.Calls[0].Args, ShouldResemble, []string{
				"puppet-check-updates", "-ensure-file", "-", "-root", "testdata/Xcode-new.app",
			})
			So(s.Calls[0].ConsumedStdin, ShouldEqual,
				"test/prefix/mac testVersion\n"+
					"test/prefix/ios testVersion\n")

			So(s.Calls[1].Executable, ShouldEqual, "sudo")
			So(s.Calls[1].Args, ShouldResemble, []string{"/usr/bin/xcode-select", "-p"})

			So(s.Calls[2].Executable, ShouldEqual, "sudo")
			So(s.Calls[2].Args, ShouldResemble, []string{"/usr/bin/xcode-select", "-s", "testdata/Xcode-new.app"})

			So(s.Calls[3].Executable, ShouldEqual, "sudo")
			So(s.Calls[3].Args, ShouldResemble, []string{"/usr/bin/xcodebuild", "-license", "accept"})

			So(s.Calls[4].Executable, ShouldEqual, "sudo")
			So(s.Calls[4].Args, ShouldResemble, []string{"/usr/bin/xcodebuild", "-runFirstLaunch"})

			So(s.Calls[5].Executable, ShouldEqual, "sudo")
			So(s.Calls[5].Args, ShouldResemble, []string{"/usr/bin/xcode-select", "-s", "old/xcode/path"})

		})
	})
}
