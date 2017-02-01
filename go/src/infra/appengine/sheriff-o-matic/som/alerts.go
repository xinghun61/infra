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
	"time"

	"golang.org/x/net/context"

	"infra/monitoring/client"
	"infra/monitoring/messages"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
)

var (
	masterStateURL = "https://chrome-internal.googlesource.com/infradata/master-manager/+/master/desired_master_state.json?format=text"
	masterStateKey = "masterState"
	// ErrUnrecognizedTree indicates that a request specificed an unrecognized tree.
	ErrUnrecognizedTree = fmt.Errorf("Unrecognized tree name")
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

func getRestartingMastersHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	tree := p.ByName("tree")

	masters, err := getRestartingMasters(c, tree)
	if err == ErrUnrecognizedTree {
		errStatus(c, w, http.StatusNotFound, err.Error())
		return
	}

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	data, err := json.Marshal(masters)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

type desiredMasterStates struct {
	MasterStates map[string][]masterState `json:"master_states"`
}

type masterState struct {
	DesiredState   string `json:"desired_state"`
	TransitionTime string `json:"transition_time_utc"`
}

func getRestartingMasters(c context.Context, treeName string) (map[string]masterState, error) {
	// Chrome OS does not use master-manager to handle restarts.
	if treeName == "chromeos" {
		return nil, nil
	}

	b, err := client.GetGitilesCached(c, masterStateURL)
	if err != nil {
		return nil, err
	}

	ms := &desiredMasterStates{}
	if err := json.Unmarshal(b, ms); err != nil {
		return nil, err
	}

	trees, err := getGatekeeperTrees(c)
	if err != nil {
		return nil, err
	}

	now := time.Now().UTC()

	ret := map[string]masterState{}
	var filter = func(masterName string, masterStates []masterState) error {
		for _, state := range masterStates {
			tt, err := time.Parse(time.RFC3339Nano, state.TransitionTime)
			if err != nil {
				return err
			}

			// TODO: make this warning window configurable. This logic will include a
			// master if it is scheduled to restart at any time later than two
			// hours ago. This handles both recent and future restarts.

			if now.Sub(tt) < 2*time.Hour {
				ret[masterName] = state
			}
		}
		return nil
	}

	// For troopers, just display all of the pending restarts.
	if treeName == "trooper" {
		for masterName, states := range ms.MasterStates {
			if err := filter(masterName, states); err != nil {
				return nil, err
			}
		}
		return ret, nil
	}

	// For specific trees, filter to master specified in the config.
	cfg, ok := trees[treeName]
	if !ok {
		return nil, ErrUnrecognizedTree
	}

	for masterLoc := range cfg.Masters {
		if err := filter(masterLoc.Name(), ms.MasterStates["master."+masterLoc.Name()]); err != nil {
			return nil, err
		}
	}
	return ret, nil
}
