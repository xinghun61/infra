// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements HTTP handlers for the frontend (default) module.
package frontend

import (
	"io/ioutil"
	"net/http"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/config"
)

func landingPageHandler(c *router.Context) {
	templates.MustRender(c.Context, c.Writer, "pages/index.html", map[string]interface{}{})
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
	logging.Debugf(c, "[frontend] Received Analyze request")
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[frontend] Analyze queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	ar := &tricium.AnalyzeRequest{}
	if err := proto.Unmarshal(body, ar); err != nil {
		logging.WithError(err).Errorf(c, "[frontend] Analyze queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	if err = validateAnalyzeRequest(c, ar); err != nil {
		logging.WithError(err).Errorf(c, "[frontend] Analyze queue handler got invalid analyze request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[frontend] Analyze request (Project: %s, Git ref: %s)", ar.Project, ar.GitRef)
	if _, err := analyze(c, ar, config.LuciConfigServer); err != nil {
		logging.WithError(err).Errorf(c, "[frontend] Failed to call Tricium.Analyze")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
	}
	logging.Infof(c, "[frontend] Successfully completed analyze")
	w.WriteHeader(http.StatusOK)
}
