// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package gerritreporter implements HTTP handlers for the gerrit-reporter module.
package gerritreporter

import (
	"io/ioutil"
	"net/http"

	"github.com/golang/protobuf/proto"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
)

func launchedHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[gerrit-reporter] Launched queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	rr := &admin.ReportLaunchedRequest{}
	if err := proto.Unmarshal(body, rr); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit-reporter] Launched queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Debugf(c, "[gerrit-reporter] Report launched request for run ID: %d", rr.RunId)
	if _, err := server.ReportLaunched(c, rr); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit-reporter] Failed to call Gerrit.ReportLaunched")
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
func completedHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[gerrit-reporter] Completed queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	rr := &admin.ReportCompletedRequest{}
	if err := proto.Unmarshal(body, rr); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit-reporter] Completed queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Debugf(c, "[gerrit-reporter] Report progress request for run ID: %d", rr.RunId)
	if _, err := server.ReportCompleted(c, rr); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit-reporter] Failed to call Gerrit.ReportCompleted")
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

func resultsHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[gerrit-reporter] Results queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	rr := &admin.ReportResultsRequest{}
	if err := proto.Unmarshal(body, rr); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit-reporter] Results queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Debugf(c, "[gerrit-reporter] Report results request for run ID: %d, analyzer: %s", rr.RunId, rr.Analyzer)
	if _, err := server.ReportResults(c, rr); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit-reporter] Failed to call Gerrit.ReportResults")
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
