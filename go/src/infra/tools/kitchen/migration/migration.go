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

// chromiumBuilderToOldMasterName maps chromium tryserver builder names to
// buildbot master names.
var chromiumBuilderToOldMasterName = map[string]string{
	"linux_chromium_rel_ng": "tryserver.chromium.linux",
}

func transformChromiumTryserverMasterBuilder(master, builder string) (string, string) {
	const prefix = "LUCI "
	if !strings.HasPrefix(builder, prefix) {
		return master, builder
	}

	oldBuilder := strings.TrimPrefix(builder, prefix)
	oldMaster := chromiumBuilderToOldMasterName[oldBuilder]
	if oldMaster == "" {
		return master, builder
	}
	return oldMaster, oldBuilder
}
