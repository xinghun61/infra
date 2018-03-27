package main

import (
	"net/http"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	"go.chromium.org/luci/server/templates"
)

var templateBundle = &templates.Bundle{
	Loader:    templates.FileSystemLoader("templates"),
	DebugMode: info.IsDevAppServer,
	DefaultArgs: func(c context.Context) (templates.Args, error) {
		loginURL, err := auth.LoginURL(c, "/")
		if err != nil {
			return nil, err
		}
		logoutURL, err := auth.LogoutURL(c, "/")
		if err != nil {
			return nil, err
		}
		isAdmin, err := auth.IsMember(c, "administrators")
		if err != nil {
			return nil, err
		}
		return templates.Args{
			"AppVersion":  strings.Split(info.VersionID(c), ".")[0],
			"IsAnonymous": auth.CurrentIdentity(c) == "anonymous:anonymous",
			"IsAdmin":     isAdmin,
			"User":        auth.CurrentUser(c),
			"LoginURL":    loginURL,
			"LogoutURL":   logoutURL,
		}, nil
	},
}

// pageBase returns the middleware chain for page handlers.
func pageBase() router.MiddlewareChain {
	return standard.Base().Extend(
		templates.WithTemplates(templateBundle),
		auth.Authenticate(server.UsersAPIAuthMethod{}),
	)
}

func init() {
	r := router.New()
	standard.InstallHandlers(r)
	mw := pageBase()
	r.GET("/", mw, indexPage)

	http.DefaultServeMux.Handle("/", r)
}

func indexPage(c *router.Context) {
	templates.MustRender(c.Context, c.Writer, "pages/index.html", nil)
}

func main() {
	// TODO: Fill out for local dev instances, using 'go run' command.
}
