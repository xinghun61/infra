// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"net/http"
	"time"

	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/grpc/discovery"
	"github.com/luci/luci-go/grpc/prpc"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"
)

var templateBundle = &templates.Bundle{
	Loader:    templates.FileSystemLoader("templates"),
	DebugMode: info.IsDevAppServer,
}

func pageBase() router.MiddlewareChain {
	return gaemiddleware.BaseProd().Extend(
		templates.WithTemplates(templateBundle),
	)
}

func init() {
	r := router.New()
	gaemiddleware.InstallHandlers(r)
	r.GET("/", pageBase(), dashboard)
	http.DefaultServeMux.Handle("/", r)

	var api prpc.Server
	dashpb.RegisterChopsServiceStatusServer(&api, &dashboardService{})
	discovery.Enable(&api)
	api.InstallHandlers(r, gaemiddleware.BaseProd())
}

// TemplateService bundles a backend.Service with its backend.ServiceIncident children.
type TemplateService struct {
	Service   *backend.Service
	Incidents *[]backend.ServiceIncident
}

func dashboard(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	dates := []string{}
	for i := 0; i < 7; i++ {
		dates = append(dates, time.Now().AddDate(0, 0, -i).Format("1-2-2006"))
	}

	monorail, err := backend.GetService(c, "monorail")
	if err != nil {
		http.Error(w, "Failed to query datastore, see logs", http.StatusInternalServerError)
		return
	}

	// TODO(jojwang): Once backend.GetServiceIncidents is added, use it
	// to get incidents.
	Services := []TemplateService{
		{Service: monorail},
	}
	NonSLAServices := []TemplateService{}

	templates.MustRender(c, w, "pages/dash.tmpl", templates.Args{
		"ChopsServices":  &Services,
		"NonSLAServices": &NonSLAServices,
		"Dates":          dates,
	})
}
