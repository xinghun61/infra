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
	const prefix = "LUCI "
	if !strings.HasPrefix(builder, prefix) {
		return master, builder
	}

	oldBuilder := strings.TrimPrefix(builder, prefix)
	var oldMaster string
	switch {
	case strings.Contains(oldBuilder, "_angle_"):
		oldMaster = "tryserver.chromium.angle"

	case
		strings.HasPrefix(oldBuilder, "android_"),
		strings.HasPrefix(oldBuilder, "linux_android_"),
		oldBuilder == "cast_shell_android":

		oldMaster = "tryserver.chromium.android"

	case strings.HasPrefix(oldBuilder, "mac_"), strings.HasPrefix(oldBuilder, "ios-"):
		oldMaster = "tryserver.chromium.mac"

	case strings.HasPrefix(oldBuilder, "win"):
		// The prefix is not "win_" because some builders start with "win<number>".
		oldMaster = "tryserver.chromium.win"

	default:
		oldMaster = "tryserver.chromium.linux"
	}
	return oldMaster, oldBuilder
}
