// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ts

import (
	"encoding/json"
	"html/template"
	"net/http"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth/xsrf"
	"go.chromium.org/luci/server/router"
)

const (
	productionAnalyticsID = "UA-55762617-27"
	stagingAnalyticsID    = "UA-55762617-27"
)

var (
	mainPage = template.Must(template.ParseFiles("./index.html"))
)

var errStatus = func(c context.Context, w http.ResponseWriter, status int, msg string) {
	logging.Errorf(c, "Status %d msg %s", status, msg)
	w.WriteHeader(status)
	w.Write([]byte(msg))
}

func base(includeCookie bool) router.MiddlewareChain {
	return standard.Base()
}

func indexPage(ctx *router.Context) {
	c, w, _, _ := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	tok, err := xsrf.Token(c)
	if err != nil {
		logging.Errorf(c, "while getting xsrf token: %s", err)
	}

	AnalyticsID := stagingAnalyticsID
	isStaging := true
	if !strings.HasSuffix(info.AppID(c), "-staging") {
		logging.Debugf(c, "Using production GA ID for app %s", info.AppID(c))
		AnalyticsID = productionAnalyticsID
		isStaging = false
	}

	data := map[string]interface{}{
		"IsDevAppServer": info.IsDevAppServer(c),
		"IsStaging":      isStaging,
		"XsrfToken":      tok,
		"AnalyticsID":    AnalyticsID,
	}

	err = mainPage.Execute(w, data)
	if err != nil {
		logging.Errorf(c, "while rendering index: %s", err)
	}
}

func getXSRFToken(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	tok, err := xsrf.Token(c)
	if err != nil {
		logging.Errorf(c, "while getting xsrf token: %s", err)
	}

	data := map[string]string{
		"token": tok,
	}
	txt, err := json.Marshal(data)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(txt)
}

//// Routes.
func init() {
	basemw := base(true)

	rootRouter := router.New()
	rootRouter.GET("/*path", basemw, indexPage)

	http.DefaultServeMux.Handle("/", rootRouter)
}
