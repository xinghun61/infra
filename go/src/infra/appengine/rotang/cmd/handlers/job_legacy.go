package handlers

import (
	"net/http"

	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"google.golang.org/appengine/log"
)

// JobLegacy updates the information served by the /legacy endpoint.
// This Job periodically updates the information and saves it to
// memcache.
func (h *State) JobLegacy(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	for k, v := range h.legacyMap {
		value, err := v(ctx, k)
		if err != nil {
			logging.Errorf(ctx.Context, "Updating legacy file: %q failed: %v", k, err)
			continue
		}

		item := memcache.NewItem(ctx.Context, k).SetValue([]byte(value))

		if err := memcache.Add(ctx.Context, item); err != nil {
			if err != memcache.ErrNotStored {
				log.Warningf(ctx.Context, "Caching value for: %q failed: %v", k, err)
				continue
			}
			if err := memcache.Set(ctx.Context, item); err != nil {
				log.Errorf(ctx.Context, "Updating value for: %q failed: %v", k, err)
				continue
			}
		}
	}
}
