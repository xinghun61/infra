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
			cv, err := configVersion.Get(c)
			So(err, ShouldBeNil)
			So(cv, ShouldEqual, 0)

			pv, err := puppetVersion.Get(c)
			So(err, ShouldBeNil)
			So(pv, ShouldEqual, "")
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

			iv, _ := configVersion.Get(c)
			So(iv, ShouldEqual, 1440131220)

			sv, _ := puppetVersion.Get(c)
			So(sv, ShouldEqual, "3.6.2")

			iv, _ = events.Get(c, "failure")
			So(iv, ShouldEqual, 1)
			iv, _ = events.Get(c, "success")
			So(iv, ShouldEqual, 2)
			iv, _ = events.Get(c, "total")
			So(iv, ShouldEqual, 0)

			iv, _ = resources.Get(c, "changed")
			So(iv, ShouldEqual, 1)
			iv, _ = resources.Get(c, "failed")
			So(iv, ShouldEqual, 2)
			iv, _ = resources.Get(c, "failed_to_restart")
			So(iv, ShouldEqual, 3)
			iv, _ = resources.Get(c, "out_of_sync")
			So(iv, ShouldEqual, 4)
			iv, _ = resources.Get(c, "restarted")
			So(iv, ShouldEqual, 5)
			iv, _ = resources.Get(c, "scheduled")
			So(iv, ShouldEqual, 6)
			iv, _ = resources.Get(c, "skipped")
			So(iv, ShouldEqual, 7)
			iv, _ = resources.Get(c, "total")
			So(iv, ShouldEqual, 51)

			fv, _ := times.Get(c, "anchor")
			So(fv, ShouldEqual, 0.01)
			fv, _ = times.Get(c, "apt_key")
			So(fv, ShouldEqual, 0.02)
			fv, _ = times.Get(c, "config_retrieval")
			So(fv, ShouldEqual, 0.03)
			fv, _ = times.Get(c, "exec")
			So(fv, ShouldEqual, 0.04)
			fv, _ = times.Get(c, "file")
			So(fv, ShouldEqual, 0.05)
			fv, _ = times.Get(c, "filebucket")
			So(fv, ShouldEqual, 0.06)
			fv, _ = times.Get(c, "package")
			So(fv, ShouldEqual, 0.07)
			fv, _ = times.Get(c, "schedule")
			So(fv, ShouldEqual, 0.08)
			fv, _ = times.Get(c, "service")
			So(fv, ShouldEqual, 0.09)
			fv, _ = times.Get(c, "total")
			So(fv, ShouldEqual, 0)

			fv, _ = age.Get(c)
			So(fv, ShouldEqual, 123.45)
		})
	})

	Convey("Puppet is_canary metric", t, func() {
		Convey("with a missing file", func() {
			So(updateIsCanary(c, "file does not exist"), ShouldBeNil)
			v, err := isCanary.Get(c)
			So(err, ShouldBeNil)
			So(v, ShouldBeFalse)
		})

		Convey("with a present file", func() {
			file, err := ioutil.TempFile("", "sysmon-puppet-test")
			So(err, ShouldBeNil)

			defer file.Close()
			defer os.Remove(file.Name())

			So(updateIsCanary(c, file.Name()), ShouldBeNil)
			v, err := isCanary.Get(c)
			So(err, ShouldBeNil)
			So(v, ShouldBeTrue)
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
				v, err := exitStatus.Get(c)
				So(err, ShouldBeNil)
				So(v, ShouldEqual, 42)
			})

			Convey(`containing a valid number and a \n`, func() {
				file.Write([]byte("42\n"))
				file.Sync()
				So(updateExitStatus(c, []string{file.Name()}), ShouldBeNil)
				v, err := exitStatus.Get(c)
				So(err, ShouldBeNil)
				So(v, ShouldEqual, 42)
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
				v, err := exitStatus.Get(c)
				So(err, ShouldBeNil)
				So(v, ShouldEqual, 42)
			})
		})
	})
}
