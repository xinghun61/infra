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
		So(uptime.Get(c), ShouldBeGreaterThan, 0)
	})

	Convey("CPU", t, func() {
		So(updateCPUMetrics(c), ShouldBeNil)
		So(cpuCount.Get(c), ShouldBeGreaterThan, 0)

		// Small fudge factor because sometimes this isn't exact.
		const aBitLessThanZero = -0.001
		const oneHundredAndABit = 100.001

		v := cpuTime.Get(c, "user")
		So(v, ShouldBeGreaterThanOrEqualTo, aBitLessThanZero)
		So(v, ShouldBeLessThanOrEqualTo, oneHundredAndABit)

		v = cpuTime.Get(c, "system")
		So(v, ShouldBeGreaterThanOrEqualTo, aBitLessThanZero)
		So(v, ShouldBeLessThanOrEqualTo, oneHundredAndABit)

		v = cpuTime.Get(c, "idle")
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

		free := diskFree.Get(c, path)
		total := diskTotal.Get(c, path)
		So(free, ShouldBeLessThanOrEqualTo, total)

		iFree := inodesFree.Get(c, path)
		iTotal := inodesTotal.Get(c, path)
		So(iFree, ShouldBeLessThanOrEqualTo, iTotal)
	})

	Convey("Memory", t, func() {
		So(updateMemoryMetrics(c), ShouldBeNil)

		free := memFree.Get(c)
		total := memTotal.Get(c)
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

		netUp.Get(c, iface)
		netDown.Get(c, iface)
	})

	Convey("Process", t, func() {
		So(updateProcessMetrics(c), ShouldBeNil)
		So(procCount.Get(c), ShouldBeGreaterThan, 0)

		if runtime.GOOS != "windows" {
			So(loadAverage.Get(c, 1), ShouldBeGreaterThan, 0)
			So(loadAverage.Get(c, 5), ShouldBeGreaterThan, 0)
			So(loadAverage.Get(c, 15), ShouldBeGreaterThan, 0)
		}
	})

	Convey("Unix time", t, func() {
		So(updateUnixTimeMetrics(c), ShouldBeNil)
		So(unixTime.Get(c), ShouldBeGreaterThan, int64(1257894000000))
	})

	Convey("OS information", t, func() {
		So(updateOSInfoMetrics(c), ShouldBeNil)

		So(osName.Get(c, ""), ShouldNotEqual, "")
		So(osVersion.Get(c, ""), ShouldNotEqual, "")
		So(osArch.Get(c), ShouldNotEqual, "")
	})
}
