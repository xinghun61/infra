// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package android

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"time"

	"github.com/luci/luci-go/common/clock"
	"golang.org/x/net/context"
)

type status string

const (
	fileVersion         = 1
	previousFileVersion = fileVersion - 1
	fileName            = "android_device_status.json"
	maxStaleness        = time.Second * 160

	notFound       status = "not_found"
	invalidJSON           = "invalid_json"
	invalidVersion        = "invalid_version"
	staleFile             = "stale_file"
	good                  = "good"
)

// deviceStatusFile is the contents of a ~/android_device_status.json file, but
// only the fields we care about.
type deviceStatusFile struct {
	Devices   map[string]deviceStatus `json:"devices"`
	Version   int                     `json:"version"`
	Timestamp float64                 `json:"timestamp"`
}

type deviceStatus struct {
	Battery   battery     `json:"battery"`
	Build     build       `json:"build"`
	Mem       memory      `json:"mem"`
	Processes int64       `json:"processes"`
	State     string      `json:"state"`
	Temp      temperature `json:"temp"`
	Uptime    float64     `json:"uptime"`
}

func (d *deviceStatus) GetStatus() string {
	if d.State == "available" {
		return "good"
	}
	return d.State
}

type battery struct {
	Level       float64 `json:"level"`
	Current     float64 `json:"current"`
	Temperature int     `json:"temperature"`
}

func (b *battery) GetTemperature() float64 {
	return float64(b.Temperature) / 10.0
}

type build struct {
	ID      string `json:"build.id"`
	Product string `json:"build_product"`
	Board   string `json:"product.board"`
	Device  string `json:"product.device"`
}

func (b *build) GetName() string {
	if b.Product != "" {
		return b.Product
	}
	if b.Board != "" {
		return b.Board
	}
	if b.Device != "" {
		return b.Device
	}
	return ""
}

type memory struct {
	Avail int64 `json:"avail"`
	Total int64 `json:"total"`
}

type temperature struct {
	EMMCTherm float64 `json:"emmc_therm"`
}

func loadFile(c context.Context, path string) (deviceStatusFile, status, error) {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return deviceStatusFile{}, notFound, err
	}

	var ret deviceStatusFile
	err = json.Unmarshal(data, &ret)
	if err != nil {
		return deviceStatusFile{}, invalidJSON, err
	}

	if ret.Version != fileVersion && ret.Version != previousFileVersion {
		return deviceStatusFile{}, invalidVersion, fmt.Errorf(
			"android device file %s is version %d, not %d", path, ret.Version, fileVersion)
	}

	ts := time.Unix(0, int64(ret.Timestamp*float64(time.Second)))
	now := clock.Now(c)
	if ts.Before(now.Add(-maxStaleness)) {
		return deviceStatusFile{}, staleFile, fmt.Errorf(
			"android device file %s is %s stale, max %s", path, now.Sub(ts), maxStaleness)
	}

	return ret, good, nil
}
