// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package system

import (
	"io/ioutil"

	"github.com/shirou/gopsutil/host"
	"golang.org/x/net/context"
)

func osInformation() (string, string, error) {
	platform, _, version, err := host.PlatformInformation()
	if err != nil {
		return "linux", "unknown", err
	}

	return platform, version, nil
}

func model(c context.Context) (string, error) {
	out, err := ioutil.ReadFile("/sys/devices/virtual/dmi/id/product_name")
	if err != nil {
		return "", err
	}
	return string(out), nil
}
