package frontend

import (
	"html/template"
	"net/http"
	"time"

	"google.golang.org/appengine"

	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"
)

func init() {
	r := router.New()
	baseMW := base()

	r.GET("/testfile", baseMW, getHandler)
	r.GET("/testfile/", baseMW, getHandler)

	http.DefaultServeMux.Handle("/", r)
}

// base returns the root middleware chain.
func base() router.MiddlewareChain {
	templateBundle := &templates.Bundle{
		Loader:    templates.FileSystemLoader("templates"),
		DebugMode: appengine.IsDevAppServer(),
		FuncMap: template.FuncMap{
			"timeParams": func(t time.Time) string {
				return t.Format(paramsTimeFormat)
			},
			"timeJS": func(t time.Time) int64 {
				return t.Unix() * 1000
			},
		},
	}

	return gaemiddleware.BaseProd().Extend(
		templates.WithTemplates(templateBundle),
	)
}
