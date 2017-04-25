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
	"github.com/luci/luci-go/server/auth/xsrf"
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

	if tree == "trooper" || tree == "milo.trooper" {
		data, err := getTrooperAlerts(c, tree == "milo.trooper")
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.Write(data)
		return
	}

	// TODO(seanmccullough): remove this check once we turn down a-d and only
	// use the cron tasks for alerts for all trees. See crbug.com/705074
	if tree == "chromium" {
		tree = "milo.chromium"
	}

	q := datastore.NewQuery("AlertJSON")
	q = q.Ancestor(datastore.MakeKey(c, "Tree", tree))
	q = q.Eq("Resolved", false)

	alertResults := []*AlertJSON{}
	err := datastore.GetAll(c, q, &alertResults)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	q = datastore.NewQuery("RevisionSummaryJSON")
	q = q.Ancestor(datastore.MakeKey(c, "Tree", tree))
	q = q.Gt("Date", clock.Get(c).Now().Add(-recentRevisions))

	revisionSummaryResults := []*RevisionSummaryJSON{}
	err = datastore.GetAll(c, q, &revisionSummaryResults)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	alertsSummary := &messages.AlertsSummary{
		Alerts:            make([]messages.Alert, len(alertResults)),
		RevisionSummaries: make(map[string]messages.RevisionSummary),
	}

	for i, alertJSON := range alertResults {
		err = json.Unmarshal(alertJSON.Contents,
			&alertsSummary.Alerts[i])
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}

		t := messages.EpochTime(alertJSON.Date.Unix())
		if alertsSummary.Timestamp == 0 || t > alertsSummary.Timestamp {
			alertsSummary.Timestamp = t
		}
	}

	for _, summaryJSON := range revisionSummaryResults {
		var summary messages.RevisionSummary
		err = json.Unmarshal(summaryJSON.Contents, &summary)
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}
		alertsSummary.RevisionSummaries[summaryJSON.ID] = summary
	}

	data, err := json.MarshalIndent(alertsSummary, "", "\t")
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

func postAlertsHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	tree := p.ByName("tree")

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

	err = putAlertsDatastore(c, tree, alertsSummary, true)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
	}
}

func putAlertsDatastore(c context.Context, tree string, alertsSummary *messages.AlertsSummary, autoResolve bool) error {
	treeKey := datastore.MakeKey(c, "Tree", tree)
	now := clock.Now(c).UTC()

	// Search for existing entities to preserve resolved status.
	alertJSONs := []*AlertJSON{}
	alertMap := make(map[string]*messages.Alert)
	for _, alert := range alertsSummary.Alerts {
		alertJSONs = append(alertJSONs, &AlertJSON{
			ID:           alert.Key,
			Tree:         treeKey,
			Resolved:     false,
			AutoResolved: false,
		})
		alertMap[alert.Key] = &alert
	}

	// Add/modify alerts.
	var err error
	err = datastore.RunInTransaction(c, func(c context.Context) error {
		// Get any existing keys to preserve resolved status, assign updated content.
		datastore.Get(c, alertJSONs)
		for i, alert := range alertsSummary.Alerts {
			alertJSONs[i].Date = now
			alertJSONs[i].Contents, err = json.Marshal(alert)
			if err != nil {
				return err
			}
			// Unresolve autoresolved alerts.
			if alertJSONs[i].Resolved && alertJSONs[i].AutoResolved {
				alertJSONs[i].Resolved = false
				alertJSONs[i].AutoResolved = false
			}
		}
		return datastore.Put(c, alertJSONs)
	}, nil)
	if err != nil {
		return err
	}

	if autoResolve {
		alertJSONs = []*AlertJSON{}
		err = datastore.RunInTransaction(c, func(c context.Context) error {
			q := datastore.NewQuery("AlertJSON")
			q = q.Ancestor(treeKey)
			q = q.Eq("Resolved", false)
			openAlerts := []*AlertJSON{}
			err = datastore.GetAll(c, q, &openAlerts)
			if err != nil {
				return err
			}
			for _, alert := range openAlerts {
				if _, modified := alertMap[alert.ID]; !modified {
					alert.Resolved = true
					alert.AutoResolved = true
					alert.ResolvedDate = now
					alertJSONs = append(alertJSONs, alert)
				}
			}
			return datastore.Put(c, alertJSONs)
		}, nil)
		if err != nil {
			return err
		}
	}

	revisionSummaryJSONs := make([]RevisionSummaryJSON,
		len(alertsSummary.RevisionSummaries))
	i := 0
	for key, summary := range alertsSummary.RevisionSummaries {
		revisionSummaryJSONs[i].ID = key
		revisionSummaryJSONs[i].Tree = treeKey
		revisionSummaryJSONs[i].Date = now
		revisionSummaryJSONs[i].Contents, err = json.Marshal(summary)
		if err != nil {
			return err
		}

		i++
	}

	return datastore.Put(c, revisionSummaryJSONs)
}

func postAlertHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	tree := p.ByName("tree")
	key := p.ByName("key")

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
	alert := &messages.Alert{}
	err = json.Unmarshal(data, alert)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	if key != alert.Key {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("POST key '%s' does not match alert key '%s'", key, alert.Key))
		return
	}

	alertJSON := &AlertJSON{
		ID:       key,
		Tree:     datastore.MakeKey(c, "Tree", tree),
		Resolved: false,
	}

	err = datastore.RunInTransaction(c, func(c context.Context) error {
		// Try and get the alert to maintain resolved status.
		datastore.Get(c, alertJSON)
		alertJSON.Date = clock.Now(c)
		alertJSON.Contents = data
		if alertJSON.Resolved && alertJSON.AutoResolved {
			alertJSON.Resolved = false
			alertJSON.AutoResolved = false
		}
		return datastore.Put(c, alertJSON)
	}, nil)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
}

func resolveAlertHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	tree := p.ByName("tree")
	treeKey := datastore.MakeKey(c, "Tree", tree)
	now := clock.Now(c).UTC()

	req := &postRequest{}
	err := json.NewDecoder(r.Body).Decode(req)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("while decoding request: %s", err))
		return
	}

	if err := xsrf.Check(c, req.XSRFToken); err != nil {
		errStatus(c, w, http.StatusForbidden, err.Error())
		return
	}

	if err := r.Body.Close(); err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	if req.Data == nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}
	resolveRequest := &ResolveRequest{}
	err = json.Unmarshal(*req.Data, resolveRequest)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	alertJSONs := make([]AlertJSON, len(resolveRequest.Keys))
	for i, key := range resolveRequest.Keys {
		alertJSONs[i].ID = key
		alertJSONs[i].Tree = treeKey
	}

	err = datastore.RunInTransaction(c, func(c context.Context) error {
		datastore.Get(c, alertJSONs)
		for i := range resolveRequest.Keys {
			if len(alertJSONs[i].Contents) == 0 {
				return fmt.Errorf("Key %s not found", alertJSONs[i].ID)
			}
			alertJSONs[i].Resolved = resolveRequest.Resolved
			alertJSONs[i].AutoResolved = false
			alertJSONs[i].ResolvedDate = now
		}
		return datastore.Put(c, alertJSONs)
	}, nil)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	resolveResponse := &ResolveResponse{
		Tree:     tree,
		Keys:     resolveRequest.Keys,
		Resolved: resolveRequest.Resolved,
	}
	resp, err := json.Marshal(resolveResponse)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(resp)
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
