// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package app implements chromium-build-stats.appspot.com services.
package main

import (
	"bufio"
	"fmt"
	"net/http"
	"path"
	"regexp"
	"strings"

	"google.golang.org/appengine"
	"google.golang.org/appengine/urlfetch"
)

const (
	topHTML = `
<html>
<head><title>chromium-build-stats</title></head>
<body>
<h1>chromium-build-stats</h1>
<form action="/">
<label for="loc">compile step URL or gs URI:</label><input type="text" name="loc" />
<input type="submit" value="submit"><input type="reset">
</form>

<hr />
See <a href="https://docs.google.com/a/chromium.org/document/d/16TdPTIIZbtAarXZIMJdiT9CePG5WYCrdxm5u9UuHXNY/edit?pli=1#heading=h.xgjl2srtytjt">design doc</a>
</body>
</html>
`
)

var ninjaLogRE = regexp.MustCompile(`gs://chrome-goma-log/.*/ninja_log.*\.gz`)

func init() {
	// This is handler to check whether ninja log can be uploaded or not from
	// depot_tools user.
	http.HandleFunc("/should-upload", shouldUploadHandler)

	http.HandleFunc("/", handler)
}

// This code is copied from https://chromium.googlesource.com/infra/infra/+/b74c3b27b1fb8f60c969e9f158c86d49b56f3d4b/go/src/infra/appengine/depot_tools_metrics/metrics/app.go#52
// shouldUploadHandler handles the '/should-upload' endpoint, which is used by
// depot_tools to check whether it should collect and upload metrics.
// It returns 200 if the request in coming from a corp machine, and thus a
// Googler, and 403 otherwise.
func shouldUploadHandler(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/should-upload" {
		http.NotFound(w, r)
		return
	}
	// TRUSTED_IP_REQUEST=1 means the request is coming from a corp machine.
	if r.Header.Get("X-AppEngine-Trusted-IP-Request") != "1" {
		http.Error(w, "Access Denied: You're not on corp.", http.StatusForbidden)
		return
	}
	fmt.Fprintf(w, "Success")
}

func handler(w http.ResponseWriter, req *http.Request) {
	loc := req.FormValue("loc")
	if loc != "" {
		if strings.HasPrefix(loc, "http://build.chromium.org/") {
			ctx := appengine.NewContext(req)
			client := urlfetch.Client(ctx)
			resp, err := client.Get(loc)
			if err != nil {
				http.Error(w, err.Error(), http.StatusBadRequest)
				return
			}
			defer resp.Body.Close()
			if resp.StatusCode != 200 {
				http.Error(w, fmt.Sprintf("%s reply %s", loc, resp.Status), resp.StatusCode)
				return
			}
			s := bufio.NewScanner(resp.Body)
			for s.Scan() {
				if m := ninjaLogRE.Find(s.Bytes()); m != nil {
					loc = string(m)
					break
				}
			}
			if err := s.Err(); err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
		}

		if strings.HasPrefix(loc, "gs://chrome-goma-log") {
			logPath := strings.TrimPrefix(loc, "gs://chrome-goma-log")
			basename := path.Base(loc)
			switch {
			case strings.HasPrefix(basename, "ninja_log."):
				http.Redirect(w, req, "/ninja_log"+logPath, http.StatusSeeOther)
				return
			case strings.HasPrefix(basename, "compiler_proxy."):
				http.Redirect(w, req, "/compiler_proxy_log"+logPath, http.StatusSeeOther)
				return
			}
		}
		http.NotFound(w, req)
		return
	}
	w.Header().Set("Content-Type", "text/html")
	fmt.Fprintf(w, topHTML)
}
