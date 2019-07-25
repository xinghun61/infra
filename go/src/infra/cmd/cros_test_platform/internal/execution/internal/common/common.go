// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package common implements some common functions shared between autotest and
// skylab executors.
package common

import (
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/luci/common/errors"
)

// Builds describes the build names that were requested by a test_platform
// invocation.
type Builds struct {
	ChromeOS   string
	FirmwareRW string
	FirmwareRO string
}

// ExtractBuilds extracts builds that were requested by the test_platform invocation.
func ExtractBuilds(deps []*test_platform.Request_Params_SoftwareDependency) (*Builds, error) {
	b := &Builds{}
	for _, dep := range deps {
		switch d := dep.Dep.(type) {
		case *test_platform.Request_Params_SoftwareDependency_ChromeosBuild:
			if already := b.ChromeOS; already != "" {
				return nil, errors.Reason("duplicate ChromeOS builds (%s, %s)", already, d.ChromeosBuild).Err()
			}
			b.ChromeOS = d.ChromeosBuild
		case *test_platform.Request_Params_SoftwareDependency_RoFirmwareBuild:
			if already := b.FirmwareRO; already != "" {
				return nil, errors.Reason("duplicate RO Firmware builds (%s, %s)", already, d.RoFirmwareBuild).Err()
			}
			b.FirmwareRO = d.RoFirmwareBuild
		case *test_platform.Request_Params_SoftwareDependency_RwFirmwareBuild:
			if already := b.FirmwareRW; already != "" {
				return nil, errors.Reason("duplicate RW Firmware builds (%s, %s)", already, d.RwFirmwareBuild).Err()
			}
			b.FirmwareRW = d.RwFirmwareBuild
		default:
			return nil, errors.Reason("unknown dep %+v", dep).Err()
		}
	}
	return b, nil
}
