// Package migration contains code specific to migration of Chrome
// Infrastructure to LUCI Lite.
package migration

import (
	"strings"

	"github.com/luci/luci-go/common/errors"
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
	case strings.HasPrefix(oldBuilder, "linux_"):
		oldMaster = "tryserver.chromium.linux"
	case strings.HasPrefix(oldBuilder, "mac_"):
		oldMaster = "tryserver.chromium.mac"
	case strings.HasPrefix(oldBuilder, "win_"):
		oldMaster = "tryserver.chromium.win"
	default:
		return master, builder
	}
	return oldMaster, oldBuilder
}
