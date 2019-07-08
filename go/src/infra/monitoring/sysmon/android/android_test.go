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

	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/tsmon"
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
				So(ioutil.WriteFile(filepath.Join(path, fileName), []byte(`{"version": 1, "timestamp": 946782245, "devices": {}}`), 0644), ShouldBeNil)
			}
			So(update(c, tmpPath), ShouldBeNil)
		})
		Convey("loads a number of broken files", func() {
			for _, fileName := range fileNames {
				So(ioutil.WriteFile(filepath.Join(path, fileName), []byte(`not json`), 0644), ShouldBeNil)
			}
			So(update(c, tmpPath), ShouldNotBeNil)
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
					IMEI: "123456789",
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

		So(cpuTemp.Get(c, "02eccd9208ead9ab"), ShouldEqual, 23)
		So(battTemp.Get(c, "02eccd9208ead9ab"), ShouldEqual, 24.8)
		So(battCharge.Get(c, "02eccd9208ead9ab"), ShouldEqual, 100)
		So(devOS.Get(c, "02eccd9208ead9ab"), ShouldEqual, "KTU84P")
		So(devStatus.Get(c, "02eccd9208ead9ab", "123456789"), ShouldEqual, "good")
		So(devType.Get(c, "02eccd9208ead9ab"), ShouldEqual, "hammerhead")
		So(devUptime.Get(c, "02eccd9208ead9ab"), ShouldEqual, 1159.48)
		So(memFree.Get(c, "02eccd9208ead9ab"), ShouldEqual, 1279052)
		So(memTotal.Get(c, "02eccd9208ead9ab"), ShouldEqual, 1899548)
		So(procCount.Get(c, "02eccd9208ead9ab"), ShouldEqual, 179)
	})
}
