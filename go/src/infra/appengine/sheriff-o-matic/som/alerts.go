// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to default module.
package som

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"

	"infra/monitoring/messages"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
)

func getAlertsHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	tree := p.ByName("tree")

	if tree == "trooper" {
		data, err := getTrooperAlerts(c)
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.Write(data)
		return
	}

	results := []*AlertsJSON{}
	q := datastore.NewQuery("AlertsJSON")
	q = q.Ancestor(datastore.MakeKey(c, "Tree", tree))
	q = q.Order("-Date")
	q = q.Limit(1)

	err := datastore.GetAll(c, q, &results)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	if len(results) == 0 {
		logging.Warningf(c, "No alerts found for tree %s", tree)
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("Tree \"%s\" not found", tree))
		return
	}

	alertsJSON := results[0]
	w.Header().Set("Content-Type", "application/json")
	w.Write(alertsJSON.Contents)
}

func postAlertsHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	tree := p.ByName("tree")

	alerts := AlertsJSON{
		Tree: datastore.MakeKey(c, "Tree", tree),
		Date: clock.Now(c),
	}
	data, err := ioutil.ReadAll(r.Body)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	if err := r.Body.Close(); err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	// Do a sanity check.
	alertsSummary := &messages.AlertsSummary{}
	err = json.Unmarshal(data, alertsSummary)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	if alertsSummary.Timestamp == 0 {
		errStatus(c, w, http.StatusBadRequest,
			"Couldn't decode into AlertsSummary or did not include a timestamp.")
		return
	}

	// Now actually do decoding necessary for storage.
	out := make(map[string]interface{})
	err = json.Unmarshal(data, &out)

	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	out["date"] = alerts.Date.String()
	data, err = json.Marshal(out)

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	alerts.Contents = data
	err = datastore.Put(c, &alerts)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
}
