// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package chromiumbuildstats

// file.go provides /file endpoints.

import (
	"io"
	"net/http"
	"strings"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/appengine"
	"google.golang.org/appengine/log"
	"google.golang.org/appengine/urlfetch"
	"google.golang.org/appengine/user"

	"infra/appengine/chromium_build_stats/logstore"
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
	if !strings.HasSuffix(user.Email, "@google.com") {
		http.Error(w, "Unauthorized to access", http.StatusUnauthorized)
		return
	}

	client := &http.Client{
		Transport: &oauth2.Transport{
			Source: google.AppEngineTokenSource(ctx, "https://www.googleapis.com/auth/devstorage.read_only"),
			Base: &urlfetch.Transport{
				Context: ctx,
			},
		},
	}
	path := req.URL.Path
	resp, err := logstore.Fetch(client, path)
	if err != nil {
		log.Errorf(ctx, "failed to fetch %s: %v", path, err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()
	copyHeader(w.Header(), resp.Header)
	w.WriteHeader(resp.StatusCode)
	_, err = io.Copy(w, resp.Body)
	if err != nil {
		log.Errorf(ctx, "failed to copy %s: %v", path, err)
	}
}

func copyHeader(dst, src http.Header) {
	for k, vv := range src {
		if strings.HasPrefix(k, "X-") {
			continue
		}
		for _, v := range vv {
			dst.Add(k, v)
		}
	}
}
