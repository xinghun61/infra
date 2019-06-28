// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"html/template"
	"io/ioutil"
	"net/http"
	"strings"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/config"
)

func mainPageHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	args, err := templateArgs(c, r)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to get template args.")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	t, err := template.ParseFiles("ui/build/default/index.html")
	if err != nil {
		logging.Errorf(c, "Failed to get parse built HTML, falling back.")
		t = template.Must(template.ParseFiles("ui/index.html"))
	}
	if err = t.Execute(w, args); err != nil {
		logging.WithError(err).Errorf(c, "Failed to render frontend UI.")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
}

func templateArgs(c context.Context, r *http.Request) (map[string]interface{}, error) {
	dest := r.URL.EscapedPath()
	loginURL, err := auth.LoginURL(c, dest)
	if err != nil {
		return nil, err
	}
	logoutURL, err := auth.LogoutURL(c, dest)
	if err != nil {
		return nil, err
	}
	return templates.Args{
		"AppVersion":  strings.Split(info.VersionID(c), ".")[0],
		"IsAnonymous": auth.CurrentIdentity(c) == "anonymous:anonymous",
		"User":        auth.CurrentUser(c).Email,
		"LoginURL":    loginURL,
		"LogoutURL":   logoutURL,
	}, nil
}

// analyzeHandler calls Tricium.Analyze for entries in the analyze queue.
//
// This queue is intended as a service extension point for modules
// running within the Tricium GAE app, such as the Gerrit poller.
// TODO(qyearsley): Figure out whether this queue is needed; if
// the Gerrit poller can directly add RPC requests to the queue
// then this would be unnecessary.
func analyzeHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to read request body.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	ar := &tricium.AnalyzeRequest{}
	if err := proto.Unmarshal(body, ar); err != nil {
		logging.WithError(err).Errorf(c, "Failed to unmarshal request.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	if err = validateAnalyzeRequest(c, ar); err != nil {
		logging.WithError(err).Errorf(c, "Got an invalid Analyze request.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	runID, err := analyze(c, ar, config.LuciConfigServer)
	logging.Fields{
		"runID": runID,
	}.Infof(c, "Received request.")
	if err != nil {
		logging.WithError(err).Errorf(c, "Analyze failed.")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	w.WriteHeader(http.StatusOK)
}
