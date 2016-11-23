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

	"infra/monitoring/messages"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/memcache"
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

	// Get from memecache first.
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
	item, err := memcache.GetKey(c, gatekeeperTreesKey)
	if err != nil && err != memcache.ErrCacheMiss {
		return nil, err
	}

	var b []byte
	if err == memcache.ErrCacheMiss {
		b, err = getGitiles(c, masterStateURL)
		item = memcache.NewItem(c, masterStateKey).SetValue(b).SetExpiration(5 * time.Minute)
		err = memcache.Set(c, item)
	}

	if err != nil {
		return nil, err
	}

	ms := &desiredMasterStates{}
	if err := json.Unmarshal(item.Value(), ms); err != nil {
		return nil, err
	}

	trees, err := getGatekeeperTrees(c)
	if err != nil {
		return nil, err
	}

	treeCfg, ok := trees[treeName]
	if !ok {
		return nil, ErrUnrecognizedTree
	}

	now := time.Now().UTC()

	ret := map[string]masterState{}
	for masterLoc := range treeCfg.Masters {
		for _, ds := range ms.MasterStates["master."+masterLoc.Name()] {
			tt, err := time.Parse(time.RFC3339Nano, ds.TransitionTime)
			if err != nil {
				return nil, err
			}

			// TODO: make this warning window configurable. This logic will include a
			// master if it is scheduled to restart at any time later than two
			// hours ago. This handles both recent and future restarts.
			if now.Sub(tt) < 2*time.Hour {
				ret[masterLoc.Name()] = ds
			}
		}
	}

	return ret, nil
}
