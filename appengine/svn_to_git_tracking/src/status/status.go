// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package status

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
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

type whitelistedHost struct {
}

func init() {
	http.HandleFunc("/api/reportState", reportState)
	http.HandleFunc("/api/whitelistHost", whitelistHost)
	http.HandleFunc("/api/pending", pendingHosts)
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

	q:= datastore.NewQuery("whitelistedHost").KeysOnly()
	whitelistedHosts, err := q.GetAll(c, nil)
	if err != nil {
		c.Errorf("Failed to get whitelisted hosts: %s", err)
		http.Error(w, "Failed to get whitelisted hosts", http.StatusInternalServerError)
		return
	}

	convert := false
	if state == "SVN" {
		for _, wh := range whitelistedHosts {
			whitelistedHost := strings.ToLower(wh.StringID())
			host = strings.ToLower(host)
			if strings.Contains(host, whitelistedHost) {
				convert = true
				break
			}
		}
	}

	out, err := json.Marshal(convert)
	if err != nil {
		c.Errorf("Failed to encode conversion status as JSON: %s", err)
		http.Error(w, "Failed to encode conversion status as  JSON", http.StatusInternalServerError)
		return
	}
	fmt.Fprintln(w, string(out))
}

func whitelistHost(w http.ResponseWriter, r *http.Request) {
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

	c := appengine.NewContext(r)
	wh := whitelistedHost{}
	whKey := datastore.NewKey(c, "whitelistedHost", host, 0, nil)
	if _, err := datastore.Put(c, whKey, &wh); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	fmt.Fprintln(w, "Done")
}

func pendingHosts(w http.ResponseWriter, r *http.Request) {
	c := appengine.NewContext(r)
	q1 := datastore.NewQuery("hostLatestState").Filter("State=", "SVN").KeysOnly()
	svnHosts, err := q1.GetAll(c, nil)
	if err != nil {
		c.Errorf("Failed to get host states: %s", err)
		http.Error(w, "Failed to get host states", http.StatusInternalServerError)
		return
	}

	q2:= datastore.NewQuery("whitelistedHost").KeysOnly()
	whitelistedHosts, err := q2.GetAll(c, nil)
	if err != nil {
		c.Errorf("Failed to get whitelisted hosts: %s", err)
		http.Error(w, "Failed to get whitelisted hosts", http.StatusInternalServerError)
		return
	}

	pendingHosts := make([]string, 0)
	for _, host := range whitelistedHosts {
		whitelistedHost := strings.ToLower(host.StringID())
		for _, host2 := range svnHosts {
			svnHost := strings.ToLower(host2.StringID())
			if strings.Contains(svnHost, whitelistedHost) {
				pendingHosts = append(pendingHosts, svnHost)
			}
		}
	}

	out, err := json.Marshal(pendingHosts)
	if err != nil {
		c.Errorf("Failed to encode list of pending hosts as JSON: %s", err)
		http.Error(w, "Failed to encode list of pending hosts as JSON", http.StatusInternalServerError)
		return
	}

	fmt.Fprintln(w, string(out))
}
