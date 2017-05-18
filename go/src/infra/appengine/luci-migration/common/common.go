package common

import (
	"strings"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/info"
)

// IsDevInstance returns true if this is a dev server of the app.
func IsDevInstance(c context.Context) bool {
	return strings.HasSuffix(info.AppID(c), "-dev") || info.IsDevAppServer(c)
}
