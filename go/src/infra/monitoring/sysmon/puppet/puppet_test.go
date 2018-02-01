// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package puppet

import (
	"io/ioutil"
	"os"
	"testing"
	"time"

	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/tsmon"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMetrics(t *testing.T) {
	c := context.Background()
	c, _ = tsmon.WithDummyInMemory(c)
	c, _ = testclock.UseTime(c, time.Unix(1440132466, 0).Add(123450*time.Millisecond))

	Convey("Puppet last_run_summary.yaml metrics", t, func() {
		file, err := ioutil.TempFile("", "sysmon-puppet-test")
		So(err, ShouldBeNil)

		defer file.Close()
		defer os.Remove(file.Name())

		Convey("with an empty file", func() {
			So(updateLastRunStats(c, file.Name()), ShouldBeNil)
			So(configVersion.Get(c), ShouldEqual, 0)
			So(puppetVersion.Get(c), ShouldEqual, "")
		})

		Convey("with a missing file", func() {
			So(updateLastRunStats(c, "file does not exist"), ShouldNotBeNil)
		})

		Convey("with an invalid file", func() {
			file.Write([]byte("\""))
			file.Sync()
			So(updateLastRunStats(c, file.Name()), ShouldNotBeNil)
		})

		Convey("with a file containing an array", func() {
			file.Write([]byte("- one\n- two\n"))
			file.Sync()
			So(updateLastRunStats(c, file.Name()), ShouldNotBeNil)
		})

		Convey("metrics", func() {
			file.Write([]byte(`---
  version:
    config: 1440131220
    puppet: "3.6.2"
  resources:
    changed: 1
    failed: 2
    failed_to_restart: 3
    out_of_sync: 4
    restarted: 5
    scheduled: 6
    skipped: 7
    total: 51
  time:
    anchor: 0.01
    apt_key: 0.02
    config_retrieval: 0.03
    exec: 0.04
    file: 0.05
    filebucket: 0.06
    package: 0.07
    schedule: 0.08
    service: 0.09
    total: 0.10
    last_run: 1440132466
  changes:
    total: 4
  events:
    failure: 1
    success: 2
    total: 3`))
			file.Sync()
			So(updateLastRunStats(c, file.Name()), ShouldBeNil)

			So(configVersion.Get(c), ShouldEqual, 1440131220)
			So(puppetVersion.Get(c), ShouldEqual, "3.6.2")

			So(events.Get(c, "failure"), ShouldEqual, 1)
			So(events.Get(c, "success"), ShouldEqual, 2)
			So(events.Get(c, "total"), ShouldEqual, 0)

			So(resources.Get(c, "changed"), ShouldEqual, 1)
			So(resources.Get(c, "failed"), ShouldEqual, 2)
			So(resources.Get(c, "failed_to_restart"), ShouldEqual, 3)
			So(resources.Get(c, "out_of_sync"), ShouldEqual, 4)
			So(resources.Get(c, "restarted"), ShouldEqual, 5)
			So(resources.Get(c, "scheduled"), ShouldEqual, 6)
			So(resources.Get(c, "skipped"), ShouldEqual, 7)
			So(resources.Get(c, "total"), ShouldEqual, 51)

			So(times.Get(c, "anchor"), ShouldEqual, 0.01)
			So(times.Get(c, "apt_key"), ShouldEqual, 0.02)
			So(times.Get(c, "config_retrieval"), ShouldEqual, 0.03)
			So(times.Get(c, "exec"), ShouldEqual, 0.04)
			So(times.Get(c, "file"), ShouldEqual, 0.05)
			So(times.Get(c, "filebucket"), ShouldEqual, 0.06)
			So(times.Get(c, "package"), ShouldEqual, 0.07)
			So(times.Get(c, "schedule"), ShouldEqual, 0.08)
			So(times.Get(c, "service"), ShouldEqual, 0.09)
			So(times.Get(c, "total"), ShouldEqual, 0)

			So(age.Get(c), ShouldEqual, 123.45)
		})
	})

	Convey("Puppet is_canary metric", t, func() {
		Convey("with a missing file", func() {
			So(updateIsCanary(c, "file does not exist"), ShouldBeNil)
			So(isCanary.Get(c), ShouldBeFalse)
		})

		Convey("with a present file", func() {
			file, err := ioutil.TempFile("", "sysmon-puppet-test")
			So(err, ShouldBeNil)

			defer file.Close()
			defer os.Remove(file.Name())

			So(updateIsCanary(c, file.Name()), ShouldBeNil)
			So(isCanary.Get(c), ShouldBeTrue)
		})
	})

	Convey("Puppet exit_status metric", t, func() {
		Convey("with a missing file", func() {
			err := updateExitStatus(c, []string{"file does not exist"})
			So(err, ShouldNotBeNil)
		})

		Convey("with a present file", func() {
			file, err := ioutil.TempFile("", "sysmon-puppet-test")
			So(err, ShouldBeNil)

			Convey("containing a valid number", func() {
				file.Write([]byte("42"))
				file.Sync()
				So(updateExitStatus(c, []string{file.Name()}), ShouldBeNil)
				So(exitStatus.Get(c), ShouldEqual, 42)
			})

			Convey(`containing a valid number and a \n`, func() {
				file.Write([]byte("42\n"))
				file.Sync()
				So(updateExitStatus(c, []string{file.Name()}), ShouldBeNil)
				So(exitStatus.Get(c), ShouldEqual, 42)
			})

			Convey("containing an invalid number", func() {
				file.Write([]byte("not a number"))
				file.Sync()
				So(updateExitStatus(c, []string{file.Name()}), ShouldNotBeNil)
			})

			Convey("second in the list", func() {
				file.Write([]byte("42"))
				file.Sync()
				So(updateExitStatus(c, []string{"does not exist", file.Name()}), ShouldBeNil)
				So(exitStatus.Get(c), ShouldEqual, 42)
			})
		})
	})
}
