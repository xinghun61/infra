// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"html/template"
	"net/http"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/logging"
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
	FuncMap: template.FuncMap{
		"fmtDate": func(date time.Time) string {
			return date.Format("1-02-2006")
		},
	},
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
	Service   backend.Service
	Incidents []backend.ServiceIncident
}

func createServicesPageData(c context.Context) (sla []TemplateService, nonSLA []TemplateService, err error) {
	services, e := backend.GetAllServices(c)
	if e != nil {
		logging.Errorf(c, "Error getting Service entities %v", e)
		return nil, nil, e
	}

	for _, service := range services {
		incidents, e := backend.GetServiceIncidents(c, service.ID, false)
		if err != nil {
			logging.Errorf(c, "Error getting ServiceIncident entities %v", e)
			return nil, nil, e
		}
		templateService := TemplateService{service, incidents}
		if service.SLA == "" {
			nonSLA = append(nonSLA, templateService)
		} else {
			sla = append(sla, templateService)
		}
	}
	return

}

func dashboard(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	dates := []time.Time{}
	for i := 0; i < 7; i++ {
		dates = append(dates, time.Now().AddDate(0, 0, -i))
	}

	sla, nonSLA, err := createServicesPageData(c)
	if err != nil {
		http.Error(w, "Failed to create Services page data, see logs",
			http.StatusInternalServerError)
		return
	}

	templates.MustRender(c, w, "pages/dash.tmpl", templates.Args{
		"ChopsServices":  sla,
		"NonSLAServices": nonSLA,
		"Dates":          dates,
	})
}
