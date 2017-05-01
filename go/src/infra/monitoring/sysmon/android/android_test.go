// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package android

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/luci/luci-go/common/clock/testclock"
	"github.com/luci/luci-go/common/tsmon"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestFileGlobbing(t *testing.T) {
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC) // Unix timestamp 946782245
	c := context.Background()
	c, _ = testclock.UseTime(c, now)

	Convey("In a temporary directory", t, func() {
		tmpPath, err := ioutil.TempDir("", "android-devicefile-test")
		So(err, ShouldBeNil)
		defer os.RemoveAll(tmpPath)
		err = os.Mkdir(filepath.Join(tmpPath, ".android"), 0777)
		So(err, ShouldBeNil)
		path := filepath.Join(tmpPath, ".android")
		fileNames := []string{
			strings.Replace(fileGlob, "*", "file1", 1),
			strings.Replace(fileGlob, "*", "file2", 1),
			strings.Replace(fileGlob, "*", "file3", 1),
		}
		Convey("loads a number of empty files", func() {
			for _, fileName := range fileNames {
				err := ioutil.WriteFile(filepath.Join(path, fileName), []byte(`{"version": 1, "timestamp": 946782245, "devices": {}}`), 0644)
				So(err, ShouldBeNil)
			}
			err = update(c, tmpPath)
			So(err, ShouldBeNil)
		})
		Convey("loads a number of broken files", func() {
			for _, fileName := range fileNames {
				err := ioutil.WriteFile(filepath.Join(path, fileName), []byte(`not json`), 0644)
				So(err, ShouldBeNil)
			}
			err = update(c, tmpPath)
			So(err, ShouldNotBeNil)
		})
	})
}

func TestMetrics(t *testing.T) {
	c := context.Background()
	c, _ = tsmon.WithDummyInMemory(c)

	var cpu float64 = 23
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
						CPUTherm: &cpu,
						MtktsCPU: nil,
						TSensTZ0: nil,
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
