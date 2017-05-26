package som

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/memcache"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
)

// getOAuthClient returns a client capable of making HTTP requests authenticated
// with OAuth access token for userinfo.email scope.
var getOAuthClient = func(c context.Context) (*http.Client, error) {
	// Note: "https://www.googleapis.com/auth/userinfo.email" is the default
	// scope used by GetRPCTransport(AsSelf). Use auth.WithScopes(...) option to
	// override.
	t, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, err
	}
	return &http.Client{Transport: t}, nil
}

func getCrRevJSON(c context.Context, pos string) (map[string]string, error) {
	itm := memcache.NewItem(c, fmt.Sprintf("crrev:%s", pos))
	err := memcache.Get(c, itm)

	if err == memcache.ErrCacheMiss {
		hc, err := getOAuthClient(c)
		if err != nil {
			return nil, err
		}

		resp, err := hc.Get(fmt.Sprintf("https://cr-rev.appspot.com/_ah/api/crrev/v1/redirect/%s", pos))
		if err != nil {
			return nil, err
		}

		defer resp.Body.Close()
		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return nil, err
		}
		itm.SetValue(body)
		if err = memcache.Set(c, itm); err != nil {
			return nil, fmt.Errorf("while setting memcache: %s", err)
		}
	} else if err != nil {
		return nil, fmt.Errorf("while getting from memcache: %s", err)
	}

	m := map[string]string{}
	err = json.Unmarshal(itm.Value(), &m)
	if err != nil {
		return nil, err
	}

	return m, nil
}

// GetRevRangeHandler returns a revision range queury for gitiles, given one or
// two commit positions.
func GetRevRangeHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	start := p.ByName("start")
	end := p.ByName("end")
	if start == "" || end == "" {
		errStatus(c, w, http.StatusBadRequest, "Start and end parameters must be set.")
		return
	}

	itm := memcache.NewItem(c, fmt.Sprintf("revrange:%s..%s", start, end))
	err := memcache.Get(c, itm)

	if err == memcache.ErrCacheMiss {
		startRev, err := getCrRevJSON(c, start)
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}

		endRev, err := getCrRevJSON(c, end)
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}

		// TODO(seanmccullough): some sanity checking of the rev json (same repo etc)

		gitilesURL := fmt.Sprintf("https://chromium.googlesource.com/chromium/src/+log/%s^..%s?format=JSON",
			startRev["git_sha"], endRev["git_sha"])

		itm.SetValue([]byte(gitilesURL))
		if err = memcache.Set(c, itm); err != nil {
			errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("while setting memcache: %s", err))
			return
		}
	} else if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("while getting memcache: %s", err))
		return
	}

	http.Redirect(w, r, string(itm.Value()), 301)
}
