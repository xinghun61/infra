// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package system

import (
	"github.com/shirou/gopsutil/host"
)

func osInformation() (string, string, error) {
	platform, _, version, err := host.PlatformInformation()
	if err != nil {
		return "linux", "unknown", err
	}

	return platform, version, nil
}
