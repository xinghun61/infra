package handler

import (
	"fmt"
	"net/http"
	"strings"

	"infra/appengine/sheriff-o-matic/som/client"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
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

// GetRevRangeHandler returns a revision range queury for gitiles, given one or
// two commit positions.
func GetRevRangeHandler(ctx *router.Context) {
	crRev := client.NewCrRev("https://cr-rev.appspot.com")
	getRevRangeHandler(ctx, crRev)
}

func getRevRangeHandler(ctx *router.Context, crRev client.CrRev) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	host := p.ByName("host")
	repo := p.ByName("repo")
	if host == "" || repo == "" {
		errStatus(c, w, http.StatusBadRequest, "Host and repo must be set")
	}

	// Either startPos and endPos commit positions will be passed or
	// startRev and endRev revisions will be passed. If commit positions
	// are passed, we get the gitilesURL using crrev via GetRedirect.
	// If revisions are passed, we create the the gitiles url directly.
	queryValues := r.URL.Query()
	startPos := queryValues.Get("startPos")
	endPos := queryValues.Get("endPos")
	startRev := queryValues.Get("startRev")
	endRev := queryValues.Get("endRev")

	var itm memcache.Item
	if startPos != "" && endPos != "" {
		itm = memcache.NewItem(c, fmt.Sprintf("revrange:%s..%s", startPos, endPos))
	} else if startRev != "" && endRev != "" {
		itm = memcache.NewItem(c, fmt.Sprintf("revrange:%s..%s", startRev, endRev))
	} else {
		errStatus(c, w, http.StatusBadRequest, "Start and end position or revision parameters must be set.")
		return
	}

	err := memcache.Get(c, itm)

	// TODO: nix this double layer of caching.
	if err == memcache.ErrCacheMiss {
		// TODO(seanmccullough): some sanity checking of the rev json (same repo etc)
		if startRev == "" && endRev == "" {
			startRevObj, err := crRev.GetRedirect(c, startPos)
			if err != nil {
				errStatus(c, w, http.StatusInternalServerError, err.Error())
				return
			}

			endRevObj, err := crRev.GetRedirect(c, endPos)
			if err != nil {
				errStatus(c, w, http.StatusInternalServerError, err.Error())
				return
			}
			startRev = startRevObj["git_sha"]
			endRev = endRevObj["git_sha"]
		}

		// A repo name with "/" cannot be passed as a URL param. So all "/" were
		// replaced with "." before this request was made.
		repo = strings.Replace(repo, ".", "/", -1)
		gitilesURL := fmt.Sprintf("https://%s.googlesource.com/%s/+log/%s^..%s?format=JSON",
			host, repo, startRev, endRev)

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
