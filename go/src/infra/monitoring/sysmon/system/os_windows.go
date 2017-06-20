// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package system

import (
	"fmt"
	"strings"

	"github.com/StackExchange/wmi"
	"golang.org/x/net/context"
)

// Win32_OperatingSystem contains fields from the WMI class with the same name:
// https://msdn.microsoft.com/en-us/library/aa394239(v=vs.85).aspx
type Win32_OperatingSystem struct {
	Version     string
	ProductType uint32
}

// Win32_ComputerSystem contains fields from the WMI class with the same name:
// https://msdn.microsoft.com/en-us/library/aa394102(v=vs.85).aspx
type Win32_ComputerSystem struct {
	Model string
}

var cachedOSInfo *Win32_OperatingSystem
var cachedSystemInfo *Win32_ComputerSystem

const workstationType uint32 = 1

func osInformation() (string, string, error) {
	if cachedOSInfo == nil {
		var dst []Win32_OperatingSystem
		q := wmi.CreateQuery(&dst, "")
		err := wmi.Query(q, &dst)
		if err != nil {
			return "win", "unknown", err
		}

		cachedOSInfo = &dst[0]
	}

	versionParts := strings.Split(cachedOSInfo.Version, ".")
	if len(versionParts) < 2 {
		return "win", "unknown", fmt.Errorf("invalid WMI version string %s", cachedOSInfo.Version)
	}

	major, minor := versionParts[0], versionParts[1]
	return "win", getOSVersion(major, minor, cachedOSInfo.ProductType), nil
}

func getOSVersion(major, minor string, productType uint32) string {
	// Versions are described in
	// https://msdn.microsoft.com/en-us/library/windows/desktop/ms724832(v=vs.85).aspx
	// Strings match Python's win32_ver in Lib/platform.py.
	majorMinor := major + "." + minor
	switch majorMinor {
	case "5.0":
		return "2000"
	case "5.1":
		return "xp"
	case "5.2":
		if productType == workstationType {
			return "xp"
		}
		return "2003Server"
	case "6.0":
		if productType == workstationType {
			return "vista"
		}
		return "2008server"
	case "6.1":
		if productType == workstationType {
			return "7"
		}
		return "2008serverR2"
	case "6.2":
		if productType == workstationType {
			return "8"
		}
		return "2012Server"
	case "6.3":
		if productType == workstationType {
			return "8.1"
		}
		return "2012ServerR2"
	case "10.0":
		if productType == workstationType {
			return "10"
		}
		return "2016Server"
	}
	return "post2016Server"
}

func model(c context.Context) (string, error) {
	if cachedSystemInfo == nil {
		var dst []Win32_ComputerSystem
		q := wmi.CreateQuery(&dst, "")
		err := wmi.Query(q, &dst)
		if err != nil {
			return "unknown", err
		}

		cachedSystemInfo = &dst[0]
	}

	return cachedSystemInfo.Model, nil
}
