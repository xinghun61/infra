// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package status

import (
	"net/http"
	"time"

	"appengine"
	"appengine/datastore"
)

type hostState struct {
	Host     string
	State    string
	Reported time.Time
}

func init() {
	http.HandleFunc("/api/reportState", reportState)
}

func reportState(w http.ResponseWriter, r *http.Request) {
	err := r.ParseForm()
	if err != nil {
		http.Error(w, "Failed to parse request parameters", http.StatusBadRequest)
		return
	}

	host, ok := r.Form["host"]
	switch {
	case !ok:
		http.Error(w, "Missing host parameter", http.StatusBadRequest)
		return
	case len(host) > 1:
		http.Error(w, "Too many host parameters", http.StatusBadRequest)
		return
	}

	state, ok := r.Form["state"]
	switch {
	case !ok:
		http.Error(w, "Missing state parameter", http.StatusBadRequest)
		return
	case len(state) > 1:
		http.Error(w, "Too many state parameters", http.StatusBadRequest)
		return
	}

	c := appengine.NewContext(r)
	hs := hostState{host[0], state[0], time.Now().UTC()}
	key := datastore.NewIncompleteKey(c, "hostState", nil)
	_, err = datastore.Put(c, key, &hs)
	if err != nil {
		http.Error(w, "Failed to store state", http.StatusInternalServerError)
		return
	}
}
