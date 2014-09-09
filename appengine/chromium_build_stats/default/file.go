// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package chromiumbuildstats

// file.go provides /file endpoints.

import (
	"io"
	"net/http"
	"strings"

	"appengine"
	"appengine/user"

	"github.com/golang/oauth2/google"
)

func init() {
	http.Handle("/file/", http.StripPrefix("/file/", http.HandlerFunc(fileHandler)))
}

// fileHandler handles /<path> to access gs://chrome-goma-log/<path>.
func fileHandler(w http.ResponseWriter, req *http.Request) {
	ctx := appengine.NewContext(req)
	user := user.Current(ctx)
	if user == nil {
		http.Error(w, "Login required", http.StatusUnauthorized)
		return
	}
	if !strings.HasSuffix(user.Email, "@chromium.org") && strings.HasSuffix(user.Email, "@google.com") {
		http.Error(w, "Unauthorized to access", http.StatusUnauthorized)
		return
	}
	config := google.NewAppEngineConfig(ctx, []string{
		"https://www.googleapis.com/auth/devstorage.read_only",
	})
	client := &http.Client{Transport: config.NewTransport()}
	path := req.URL.Path
	resp, err := fetch(client, path)
	if err != nil {
		ctx.Errorf("failed to fetch %s: %v", path, err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()
	copyHeader(w.Header(), resp.Header)
	w.WriteHeader(resp.StatusCode)
	_, err = io.Copy(w, resp.Body)
	if err != nil {
		ctx.Errorf("failed to copy %s: %v", path, err)
	}
}
