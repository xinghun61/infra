// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

// Package migration contains code specific to migration of Chrome
// Infrastructure to LUCI Lite.
package migration

import (
	"strings"

	"go.chromium.org/luci/common/errors"
)

// TransformProperties modifies props to simplify Chromium migration to LUCI.
func TransformProperties(props map[string]interface{}) error {
	masterName, ok := props["mastername"].(string)
	if !ok {
		return nil
	}

	switch masterName {
	case "luci.chromium.try":
		builderName, ok := props["buildername"].(string)
		if !ok {
			return errors.New("buildername property is not set")
		}
		props["mastername"], props["buildername"] = transformChromiumTryserverMasterBuilder(masterName, builderName)
	}
	return nil
}

func transformChromiumTryserverMasterBuilder(master, builder string) (string, string) {
	// TODO(nodir): remove a week after no build has "LUCI " builder name prefix. Do not return builder.
	builder = strings.TrimPrefix(builder, "LUCI ")
	var oldMaster string
	switch {
	case strings.Contains(builder, "_angle_"):
		oldMaster = "tryserver.chromium.angle"

	case
		strings.HasPrefix(builder, "android_"),
		strings.HasPrefix(builder, "linux_android_"),
		builder == "cast_shell_android":

		oldMaster = "tryserver.chromium.android"

	case strings.HasPrefix(builder, "mac_"), strings.HasPrefix(builder, "ios-"):
		oldMaster = "tryserver.chromium.mac"

	case strings.HasPrefix(builder, "win"):
		// The prefix is not "win_" because some builders start with "win<number>".
		oldMaster = "tryserver.chromium.win"

	default:
		oldMaster = "tryserver.chromium.linux"
	}
	return oldMaster, builder
}
