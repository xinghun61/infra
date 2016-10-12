// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package android

import (
	"testing"

	"github.com/luci/luci-go/common/tsmon"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMetrics(t *testing.T) {
	c := context.Background()
	c, _ = tsmon.WithDummyInMemory(c)

	Convey("Device metrics", t, func() {
		file := deviceStatusFile{
			Devices: map[string]deviceStatus{
				"02eccd9208ead9ab": {
					Battery: battery{
						Level:       100,
						Temperature: 248,
					},
					Build: build{
						ID:    "KTU84P",
						Board: "hammerhead",
					},
					Mem: memory{
						Avail: 1279052,
						Total: 1899548,
					},
					Processes: 179,
					State:     "available",
					Temp: temperature{
						EMMCTherm: 23,
					},
					Uptime: 1159.48,
				},
			},
			Version:   1,
			Timestamp: 9.46782245e+08,
		}

		updateFromFile(c, file)

		f, err := cpuTemp.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(f, ShouldEqual, 23)

		f, err = battTemp.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(f, ShouldEqual, 24.8)

		f, err = battCharge.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(f, ShouldEqual, 100)

		s, err := devOS.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(s, ShouldEqual, "KTU84P")

		s, err = devStatus.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(s, ShouldEqual, "good")

		s, err = devType.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(s, ShouldEqual, "hammerhead")

		f, err = devUptime.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(f, ShouldEqual, 1159.48)

		i, err := memFree.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(i, ShouldEqual, 1279052)

		i, err = memTotal.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(i, ShouldEqual, 1899548)

		i, err = procCount.Get(c, "02eccd9208ead9ab")
		So(err, ShouldBeNil)
		So(i, ShouldEqual, 179)
	})
}
