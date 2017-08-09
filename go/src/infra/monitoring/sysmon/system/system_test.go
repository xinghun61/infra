// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package system

import (
	"runtime"
	"testing"

	"go.chromium.org/luci/common/tsmon"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMetrics(t *testing.T) {
	c := context.Background()
	c, _ = tsmon.WithDummyInMemory(c)

	Convey("Uptime", t, func() {
		So(updateUptimeMetrics(c), ShouldBeNil)

		v, err := uptime.Get(c)
		So(err, ShouldBeNil)
		So(v, ShouldBeGreaterThan, 0)
	})

	Convey("CPU", t, func() {
		So(updateCPUMetrics(c), ShouldBeNil)

		// Small fudge factor because sometimes this isn't exact.
		const aBitLessThanZero = -0.001
		const oneHundredAndABit = 100.001

		v, err := cpuTime.Get(c, "user")
		So(err, ShouldBeNil)
		So(v, ShouldBeGreaterThanOrEqualTo, aBitLessThanZero)
		So(v, ShouldBeLessThanOrEqualTo, oneHundredAndABit)

		v, err = cpuTime.Get(c, "system")
		So(err, ShouldBeNil)
		So(v, ShouldBeGreaterThanOrEqualTo, aBitLessThanZero)
		So(v, ShouldBeLessThanOrEqualTo, oneHundredAndABit)

		v, err = cpuTime.Get(c, "idle")
		So(err, ShouldBeNil)
		So(v, ShouldBeGreaterThanOrEqualTo, aBitLessThanZero)
		So(v, ShouldBeLessThanOrEqualTo, oneHundredAndABit)
	})

	Convey("Disk", t, func() {
		So(updateDiskMetrics(c), ShouldBeNil)

		// A disk mountpoint that should always be present.
		path := "/"
		if runtime.GOOS == "windows" {
			path = `C:\`
		}

		free, err := diskFree.Get(c, path)
		So(err, ShouldBeNil)

		total, err := diskTotal.Get(c, path)
		So(err, ShouldBeNil)

		So(free, ShouldBeLessThanOrEqualTo, total)

		iFree, err := inodesFree.Get(c, path)
		So(err, ShouldBeNil)

		iTotal, err := inodesTotal.Get(c, path)
		So(err, ShouldBeNil)

		So(iFree, ShouldBeLessThanOrEqualTo, iTotal)
	})

	Convey("Memory", t, func() {
		So(updateMemoryMetrics(c), ShouldBeNil)

		free, err := memFree.Get(c)
		So(err, ShouldBeNil)

		total, err := memTotal.Get(c)
		So(err, ShouldBeNil)

		So(free, ShouldBeLessThanOrEqualTo, total)
	})

	Convey("Network", t, func() {
		So(updateNetworkMetrics(c), ShouldBeNil)

		// A network interface that should always be present.
		iface := "lo"
		if runtime.GOOS == "windows" {
			return // TODO(dsansome): Figure out what this is on Windows.
		} else if runtime.GOOS == "darwin" {
			iface = "en0"
		}

		_, err := netUp.Get(c, iface)
		So(err, ShouldBeNil)

		_, err = netDown.Get(c, iface)
		So(err, ShouldBeNil)
	})

	Convey("Process", t, func() {
		So(updateProcessMetrics(c), ShouldBeNil)

		v, err := procCount.Get(c)
		So(err, ShouldBeNil)
		So(v, ShouldBeGreaterThan, 0)

		if runtime.GOOS != "windows" {
			load, err := loadAverage.Get(c, 1)
			So(err, ShouldBeNil)
			So(load, ShouldBeGreaterThan, 0)

			load, err = loadAverage.Get(c, 5)
			So(err, ShouldBeNil)
			So(load, ShouldBeGreaterThan, 0)

			load, err = loadAverage.Get(c, 15)
			So(err, ShouldBeNil)
			So(load, ShouldBeGreaterThan, 0)
		}
	})

	Convey("Unix time", t, func() {
		So(updateUnixTimeMetrics(c), ShouldBeNil)

		v, err := unixTime.Get(c)
		So(err, ShouldBeNil)
		So(v, ShouldBeGreaterThan, int64(1257894000000))
	})

	Convey("OS information", t, func() {
		So(updateOSInfoMetrics(c), ShouldBeNil)

		v, err := osName.Get(c, "")
		So(err, ShouldBeNil)
		So(v, ShouldNotEqual, "")

		v, err = osVersion.Get(c, "")
		So(err, ShouldBeNil)
		So(v, ShouldNotEqual, "")

		v, err = osArch.Get(c)
		So(err, ShouldBeNil)
		So(v, ShouldNotEqual, "")
	})
}
