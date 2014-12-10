// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package helloworld

import (
	"fmt"
	"net/http"
	"runtime"

	"appengine"
	"appengine/user"

	"code.google.com/p/goauth2/oauth" // vendored packages work
	"infra/libs/build"                // infra packages work
)

func init() {
	http.HandleFunc("/", requireLogin(rootHandler))
}

func requireLogin(handler http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		c := appengine.NewContext(r)
		u := user.Current(c)
		if u == nil {
			url, err := user.LoginURL(c, r.URL.String())
			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			w.Header().Set("Location", url)
			w.WriteHeader(http.StatusFound)
			return
		}
		handler(w, r)
	}
}

func rootHandler(w http.ResponseWriter, r *http.Request) {
	c := appengine.NewContext(r)
	u := user.Current(c)
	fmt.Fprintf(w, "Hello, %v!\n", u)
	fmt.Fprintf(w, "OAuth stuff works: %v\n", &oauth.Config{})
	fmt.Fprintf(w, "Infra stuff works: %v\n", build.ReleaseBuild)
	fmt.Fprintf(w, "GOROOT: %s\n", runtime.GOROOT())
	fmt.Fprintf(w, "GOARCH: %s\n", runtime.GOARCH)
	fmt.Fprintf(w, "GOOS: %s\n", runtime.GOOS)
	fmt.Fprintf(w, "Compiler: %s\n", runtime.Compiler)
}
