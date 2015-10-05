// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package status

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"time"

	"appengine"
	"appengine/datastore"
)

type hostStateReport struct {
	Host     string
	State    string
	Reported time.Time
}

type hostLatestState struct {
	State string
}

type brokenSlave struct {
	Host      string
	ErrorType string
	Reported  time.Time
}

func init() {
	http.HandleFunc("/api/reportState", reportState)
	http.HandleFunc("/api/pending", pendingHosts)
	http.HandleFunc("/api/reportBrokenSlave", reportBrokenSlave)
	http.HandleFunc("/api/broken", brokenSlaves)
}

func getFormParam(r *http.Request, paramName string) (string, error) {
	val, ok := r.Form[paramName]
	switch {
	case !ok:
		return "", errors.New(fmt.Sprintf("Missing %s parameter", paramName))
	case len(val) > 1:
		return "", errors.New(fmt.Sprintf("Too many %s parameters", paramName))
	}

	return val[0], nil
}

func reportState(w http.ResponseWriter, r *http.Request) {
	err := r.ParseForm()
	if err != nil {
		http.Error(w, "Failed to parse request parameters", http.StatusBadRequest)
		return
	}

	host, err := getFormParam(r, "host")
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	state, err := getFormParam(r, "state")
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	c := appengine.NewContext(r)
	err = datastore.RunInTransaction(c, func(c appengine.Context) error {
		hsr := hostStateReport{host, state, time.Now().UTC()}
		hsrKey := datastore.NewIncompleteKey(c, "hostStateReport", nil)
		if _, err := datastore.Put(c, hsrKey, &hsr); err != nil {
			return err
		}

		hls := hostLatestState{state}
		hlsKey := datastore.NewKey(c, "hostLatestState", host, 0, nil)
		_, err = datastore.Put(c, hlsKey, &hls)
		return err
	}, &datastore.TransactionOptions{XG: true})

	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if state == "SVN" {
		fmt.Fprintln(w, "true")
	} else {
		fmt.Fprintln(w, "false")
	}
}

func pendingHosts(w http.ResponseWriter, r *http.Request) {
	c := appengine.NewContext(r)
	q := datastore.NewQuery("hostLatestState").Filter("State=", "SVN").KeysOnly()
	svnHosts, err := q.GetAll(c, nil)
	if err != nil {
		c.Errorf("Failed to get host states: %s", err)
		http.Error(w, "Failed to get host states", http.StatusInternalServerError)
		return
	}

	pendingHosts := make([]string, 0)
	for _, host := range svnHosts {
		pendingHosts = append(pendingHosts, host.StringID())
	}

	out, err := json.Marshal(pendingHosts)
	if err != nil {
		c.Errorf("Failed to encode list of pending hosts as JSON: %s", err)
		http.Error(w, "Failed to encode list of pending hosts as JSON", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintln(w, string(out))
}

func reportBrokenSlave(w http.ResponseWriter, r *http.Request) {
	err := r.ParseForm()
	if err != nil {
		http.Error(w, "Failed to parse request parameters", http.StatusBadRequest)
		return
	}

	host, err := getFormParam(r, "host")
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	error_type, err := getFormParam(r, "error_type")
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	c := appengine.NewContext(r)
	bs := brokenSlave{host, error_type, time.Now().UTC()}
	bsKey := datastore.NewIncompleteKey(c, "brokenSlave", nil)
	if _, err := datastore.Put(c, bsKey, &bs); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

func brokenSlaves(w http.ResponseWriter, r *http.Request) {
	c := appengine.NewContext(r)
	dayAgo := time.Now().AddDate(0, 0, -1)
	q := datastore.NewQuery("brokenSlave").Filter("Reported >", dayAgo).Project("Host", "ErrorType", "Reported").Distinct()
	var brokenSlaves []brokenSlave
	_, err := q.GetAll(c, &brokenSlaves)
	if err != nil {
		c.Errorf("Failed to get broken slaves: %s", err)
		http.Error(w, "Failed to get broken slaves", http.StatusInternalServerError)
		return
	}

	slaveErrors := make(map[string][]string)
	for _, brokenSlave := range brokenSlaves {
		if _, ok := slaveErrors[brokenSlave.ErrorType]; !ok {
			slaveErrors[brokenSlave.ErrorType] = []string{}
		}
		slaveErrors[brokenSlave.ErrorType] = append(slaveErrors[brokenSlave.ErrorType], brokenSlave.Host)
	}

	out, err := json.Marshal(slaveErrors)
	if err != nil {
		c.Errorf("Failed to encode list of slave errors as JSON: %s", err)
		http.Error(w, "Failed to encode list of slave errors as JSON", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintln(w, string(out))
}
