// Package app sets up the AppEngine routing and handlers.
package app

import (
	"net/http"

	"infra/appengine/rotang/cmd/handlers"

	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

func init() {
	r := router.New()
	standard.InstallHandlers(r)
	middleware := standard.Base()

	tmw := middleware.Extend(templates.WithTemplates(&templates.Bundle{
		Loader: templates.FileSystemLoader("../handlers/templates"),
	}))

	r.GET("/", tmw, handlers.HandleIndex)
	r.GET("/upload", tmw, handlers.HandleUpload)
	r.POST("/upload", tmw, handlers.HandleUpload)

	http.DefaultServeMux.Handle("/", r)
}
