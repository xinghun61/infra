// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"net/http"

	"github.com/gorilla/mux"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/server/router"
)

func init() {
	m := createRouter()

	// We need a LUCI router to make the middleware work.  Just delegate all
	// requests to the mux router.
	r := router.New()
	r.NotFound(gaemiddleware.BaseProd(), func(c *router.Context) { m.ServeHTTP(c.Writer, c.Request) })
	gaemiddleware.InstallHandlers(r)

	http.DefaultServeMux.Handle("/", r)
}

func createRouter() http.Handler {
	m := mux.NewRouter()

	r := m.Host("crbug.com").Subrouter()
	addCommonBugRoutes(r)
	r.Path("/").HandlerFunc(bugsHome)

	r = m.Host("www.crbug.com").Subrouter()
	addCommonBugRoutes(r)
	r.Path("/").HandlerFunc(bugsHome)

	r = m.Host("new.crbug.com").Subrouter()
	addCommonBugRoutes(r)
	r.PathPrefix("").HandlerFunc(newBugPermanent)

	return m
}

func addCommonBugRoutes(r *mux.Router) {
	r.PathPrefix("/new-detailed").HandlerFunc(newBugDetailed)
	r.PathPrefix("/new").HandlerFunc(newBug)
	r.PathPrefix("/wizard").HandlerFunc(newBugWizard)
	r.Path("/{id:[0-9]+}").HandlerFunc(bugByID)
	r.Path("/{id:[0-9]+}/").HandlerFunc(bugByID)
	r.Path("/{project:[a-z0-9][-a-z0-9]*[a-z0-9]}").HandlerFunc(projectList)
	r.Path("/{project:[a-z0-9][-a-z0-9]*[a-z0-9]}/").HandlerFunc(projectList)
	r.Path("/{project:[a-z0-9][-a-z0-9]*[a-z0-9]}/new").HandlerFunc(newBugByProject)
	r.Path("/{project:[a-z0-9][-a-z0-9]*[a-z0-9]}/new/").HandlerFunc(newBugByProject)
	r.Path("/{project:[a-z0-9][-a-z0-9]*[a-z0-9]}/{id:[0-9]+}").HandlerFunc(bugByProject)
	r.Path("/{project:[a-z0-9][-a-z0-9]*[a-z0-9]}/{id:[0-9]+}/").HandlerFunc(bugByProject)
	r.Path("/~{owner}").HandlerFunc(ownerSearch)
	r.Path("/~{owner}/").HandlerFunc(ownerSearch)
	r.Path("/{project:[a-z0-9][-a-z0-9]*[a-z0-9]}/~{owner}").HandlerFunc(ownerSearchByProject)
	r.Path("/{project:[a-z0-9][-a-z0-9]*[a-z0-9]}/~{owner}/").HandlerFunc(ownerSearchByProject)
}

func bugsHome(w http.ResponseWriter, r *http.Request) {
	http.Redirect(w, r, "https://bugs.chromium.org/p/chromium/", http.StatusFound)
}

func newBug(w http.ResponseWriter, r *http.Request) {
	http.Redirect(w, r, "https://chromiumbugs.appspot.com/", http.StatusFound)
}

func newBugPermanent(w http.ResponseWriter, r *http.Request) {
	http.Redirect(w, r, "https://chromiumbugs.appspot.com", http.StatusMovedPermanently)
}

func newBugDetailed(w http.ResponseWriter, r *http.Request) {
	http.Redirect(w, r, "https://bugs.chromium.org/p/chromium/issues/entry", http.StatusFound)
}

func newBugWizard(w http.ResponseWriter, r *http.Request) {
	http.Redirect(w, r, "https://www.google.com/accounts/ServiceLogin"+
		"?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin"+
		"%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=",
		http.StatusFound)
}

func bugByID(w http.ResponseWriter, r *http.Request) {
	v := mux.Vars(r)
	http.Redirect(w, r, fmt.Sprintf(
		"https://bugs.chromium.org/p/chromium/issues/detail?id=%s", v["id"]), http.StatusFound)
}

func projectList(w http.ResponseWriter, r *http.Request) {
	v := mux.Vars(r)
	http.Redirect(w, r, fmt.Sprintf(
		"https://bugs.chromium.org/p/%s", v["project"]), http.StatusFound)
}

func newBugByProject(w http.ResponseWriter, r *http.Request) {
	v := mux.Vars(r)
	http.Redirect(w, r, fmt.Sprintf(
		"https://bugs.chromium.org/p/%s/issues/entry", v["project"]), http.StatusFound)
}

func bugByProject(w http.ResponseWriter, r *http.Request) {
	v := mux.Vars(r)
	http.Redirect(w, r, fmt.Sprintf(
		"https://bugs.chromium.org/p/%s/issues/detail?id=%s", v["project"], v["id"]), http.StatusFound)
}

func ownerSearch(w http.ResponseWriter, r *http.Request) {
	v := mux.Vars(r)
	http.Redirect(w, r, fmt.Sprintf(
		"https://bugs.chromium.org/p/chromium/issues/list?q=owner:%s", v["owner"]), http.StatusFound)
}

func ownerSearchByProject(w http.ResponseWriter, r *http.Request) {
	v := mux.Vars(r)
	http.Redirect(w, r, fmt.Sprintf(
		"https://bugs.chromium.org/p/%s/issues/list?q=owner:%s", v["project"], v["owner"]), http.StatusFound)
}
