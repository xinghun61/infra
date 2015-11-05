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

type host struct {
	// Key is hostname
	State         string
	StateReported time.Time
}

type errorReport struct {
	// Parent is host, rey is error type
	Reported time.Time
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

	hostname, err := getFormParam(r, "host")
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
	hostKey := datastore.NewKey(c, "host", hostname, 0, nil)
	if _, err = datastore.Put(c, hostKey, &host{state, time.Now().UTC()}); err != nil {
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
	hourAgo := time.Now().Add(-time.Hour)
	q := datastore.NewQuery("host").
		Filter("State =", "SVN").
		Filter("StateReported >", hourAgo).
		KeysOnly()
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
		http.Error(w, "Failed to encode list of pending hosts as JSON",
			http.StatusInternalServerError)
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
	hostKey := datastore.NewKey(c, "host", host, 0, nil)
	errorReportKey := datastore.NewKey(c, "errorReport", error_type, 0, hostKey)
	if _, err = datastore.Put(c, errorReportKey, &errorReport{time.Now().UTC()}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

func brokenSlaves(w http.ResponseWriter, r *http.Request) {
	c := appengine.NewContext(r)
	hourAgo := time.Now().Add(-time.Hour)
	q := datastore.NewQuery("errorReport").Filter("Reported >", hourAgo)
	var errorReports []errorReport
	errorReportKeys, err := q.GetAll(c, &errorReports)
	c.Infof("Num error reports: %d", len(errorReports))
	c.Infof("Num error report keys: %d", len(errorReportKeys))
	if err != nil {
		c.Errorf("Failed to get broken slaves: %s", err)
		http.Error(w, "Failed to get broken slaves", http.StatusInternalServerError)
		return
	}

	slaveErrors := make(map[string][]string)
	for i := 0; i < len(errorReportKeys); i++ {
		hostname := errorReportKeys[i].Parent().StringID()
		error_type := errorReportKeys[i].StringID()
		if _, ok := slaveErrors[error_type]; !ok {
			slaveErrors[error_type] = make([]string, 0)
		}
		slaveErrors[error_type] = append(slaveErrors[error_type], hostname)
	}

	out, err := json.Marshal(slaveErrors)
	if err != nil {
		c.Errorf("Failed to encode list of slave errors as JSON: %s", err)
		http.Error(w, "Failed to encode list of slave errors as JSON",
			http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintln(w, string(out))
}
