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

// GetChromeOSBuild determines the ChromeOS build name specified within the
// given software dependencies (e.g. reef-release/R77-12345.0.0)
func GetChromeOSBuild(deps []*test_platform.Request_Params_SoftwareDependency) (string, error) {
	filter := func(d *test_platform.Request_Params_SoftwareDependency) bool {
		return d.GetChromeosBuild() != ""
	}
	buildDeps := filterDeps(deps, filter)

	if len(buildDeps) != 1 {
		return "", errors.Reason("get ChromeOS build: expected 1 build, got %d", len(buildDeps)).Err()
	}

	return buildDeps[0].GetChromeosBuild(), nil
}

func filterDeps(deps []*test_platform.Request_Params_SoftwareDependency, filter func(*test_platform.Request_Params_SoftwareDependency) bool) []*test_platform.Request_Params_SoftwareDependency {
	var result []*test_platform.Request_Params_SoftwareDependency
	for _, d := range deps {
		if filter(d) {
			result = append(result, d)
		}
	}
	return result
}
