// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package status

import (
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

func init() {
	http.HandleFunc("/api/reportState", reportState)
	http.HandleFunc("/", svnSlaves)
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
}

func svnSlaves(w http.ResponseWriter, r *http.Request) {
	c := appengine.NewContext(r)
	q := datastore.NewQuery("hostLatestState").Filter("State=", "SVN").KeysOnly()
	hosts, err := q.GetAll(c, nil)
	if err != nil {
		c.Errorf("Failed to get host states: %s", err)
		http.Error(w, "Failed to get host states", http.StatusInternalServerError)
		return
	}

	for _, host := range hosts {
		fmt.Fprintln(w, host.StringID())
	}
}
