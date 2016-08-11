package frontend

import (
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/luci/gae/service/memcache"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"

	"infra/appengine/test-results/builderstate"
)

// refreshFunc is the function that is called to update cached data
// or on cache miss.
// It is global to allow mocking in tests.
var refreshFunc = builderstate.RefreshCache

// GetBuilderState gets data from the builder state memcache
// and serves it as JSON.
func GetBuilderState(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	item, err := memcache.Get(c).Get(builderstate.MemcacheKey)

	if err != nil {
		item, err = refreshFunc(c)
		if err != nil {
			if err == memcache.ErrCacheMiss {
				err = fmt.Errorf("builderstate: builder data not generated: %v", err)
			}
			logging.Errorf(c, err.Error())
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
	}

	start := time.Now()

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	n, err := w.Write(item.Value())

	if err != nil {
		logging.Errorf(c, "error writing response: wrote %d bytes of %s, %s", n, item.Value(), err)
	}

	logging.Debugf(c, "took %s to write response", time.Since(start))
}

// UpdateBuilderState refreshes data in the builder state
// memcache.
func UpdateBuilderState(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	_, err := refreshFunc(c)

	if err != nil {
		logging.Errorf(c, err.Error())
		w.WriteHeader(http.StatusInternalServerError)
		io.WriteString(w, err.Error())
		return
	}

	n, err := io.WriteString(w, "OK")

	if err != nil {
		logging.Errorf(c, "error writing response: wrote %d bytes of %s, %s", n, "OK", err)
	}
}
