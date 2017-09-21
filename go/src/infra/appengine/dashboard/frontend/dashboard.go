// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"html/template"
	"net/http"
	"strconv"
	"time"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/auth/identity"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	dashpb "infra/appengine/dashboard/api/dashboard"
)

const authGroup = "chopsdash-access"

var templateBundle = &templates.Bundle{
	Loader:    templates.FileSystemLoader("templates"),
	DebugMode: info.IsDevAppServer,
	FuncMap: template.FuncMap{
		"fmtDate": func(date time.Time) string {
			return date.Format("1-2-2006")
		},
	},
}

func pageBase() router.MiddlewareChain {
	a := auth.Authenticator{
		Methods: []auth.Method{
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
			&server.InboundAppIDAuthMethod{},
			server.CookieAuth,
		},
	}
	return standard.Base().Extend(a.GetMiddleware()).Extend(
		templates.WithTemplates(templateBundle),
	)
}

func init() {
	r := router.New()
	standard.InstallHandlers(r)
	r.GET("/", pageBase(), dashboard)
	http.DefaultServeMux.Handle("/", r)

	r.GET("/old", pageBase(), oldDashboard)
	http.DefaultServeMux.Handle("/old", r)

	var api prpc.Server
	dashpb.RegisterChopsServiceStatusServer(&api, &dashboardService{})
	discovery.Enable(&api)
	api.InstallHandlers(r, standard.Base())
}

func dashboard(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	loginURL, err := auth.LoginURL(c, "/")
	if err != nil {
		http.Error(w, "failed to get login URL", http.StatusInternalServerError)
		logging.Errorf(c, "failed to get login URL: %v", err)
		return
	}
	logoutURL, err := auth.LogoutURL(c, "/")
	if err != nil {
		http.Error(w, "failed to get logout URL", http.StatusInternalServerError)
		logging.Errorf(c, "failed to get logout URL: %v", err)
		return
	}

	var isGoogler bool
	var isAnonymous bool
	var user string
	if userIdentity := auth.CurrentIdentity(c); userIdentity == identity.AnonymousIdentity {
		isAnonymous = true
		isGoogler = false
	} else {
		user = userIdentity.Email()
		isAnonymous = false
		isGoogler, err = auth.IsMember(c, authGroup)
		if err != nil {
			http.Error(w, "failed to determine membership status", http.StatusInternalServerError)
			logging.Errorf(c, "failed to determine membership status: %v", err)
			return
		}
	}

	templates.MustRender(c, w, "pages/home.html", templates.Args{
		"IsAnoymous": isAnonymous,
		"User":       user,
		"IsGoogler":  isGoogler,
		"LoginURL":   loginURL,
		"LogoutURL":  logoutURL,
	})
}

func oldDashboard(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	err := r.ParseForm()
	if err != nil {
		http.Error(w, "Failed to parse form",
			http.StatusInternalServerError)
		return
	}
	upto := r.Form.Get("upto")
	lastDate := time.Now()
	if upto != "" {
		unixInt, err := strconv.ParseInt(upto, 10, 64)
		if err != nil {
			logging.Infof(c, "%v, %v", err, lastDate)
			http.Error(w, "failed to parse \"upto\" date paramater",
				http.StatusBadRequest)
			return
		}
		dateFromParams := time.Unix(unixInt, 0)
		lastDate = dateFromParams
	}

	dates := []time.Time{}
	for i := 6; i >= 0; i-- {
		dates = append(dates, lastDate.AddDate(0, 0, -i))
	}

	// Lower limit of date span is pushed back for timezones that are behind
	// UTC and may have a current time that is still one calendar day behind the UTC
	// day. Incidents from the query that are too far back are filtered out
	// in the front end when all Dates are local.
	firstDateCushion := dates[0].AddDate(0, 0, -1)
	sla, nonSLA, err := createServicesPageData(c, firstDateCushion, lastDate)
	if err != nil {
		http.Error(w, "failed to create Services page data, see logs",
			http.StatusInternalServerError)
		return
	}

	templates.MustRender(c, w, "pages/dash.tmpl", templates.Args{
		"ChopsServices":  sla,
		"NonSLAServices": nonSLA,
		"Dates":          dates,
		"LastDate":       dates[6],
	})
}
