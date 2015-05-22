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

	"golang.org/x/net/context"

	"infra/libs/logging"
	"infra/libs/logging/gaelogger"
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

func sayHi(ctx context.Context) {
	logging.Get(ctx).Infof("Hi!")
}

func rootHandler(w http.ResponseWriter, r *http.Request) {
	c := appengine.NewContext(r)
	u := user.Current(c)
	ctx := gaelogger.Use(context.Background(), c)
	sayHi(ctx)
	fmt.Fprintf(w, "Hello, %v!\n", u)
	fmt.Fprintf(w, "GOROOT: %s\n", runtime.GOROOT())
	fmt.Fprintf(w, "GOARCH: %s\n", runtime.GOARCH)
	fmt.Fprintf(w, "GOOS: %s\n", runtime.GOOS)
	fmt.Fprintf(w, "Compiler: %s\n", runtime.Compiler)
}
