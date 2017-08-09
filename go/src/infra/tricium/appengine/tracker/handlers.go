// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package tracker implements HTTP handlers for the tracker module.
package tracker

import (
	"io/ioutil"
	"net/http"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
)

func workflowLaunchedHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[tracker] Workflow launched queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	wr := &admin.WorkflowLaunchedRequest{}
	if err := proto.Unmarshal(body, wr); err != nil {
		logging.WithError(err).Errorf(c, "[tracker] Workflow launched queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[tracker] Workflow launched request (run ID: %d)", wr.RunId)
	if _, err := server.WorkflowLaunched(c, wr); err != nil {
		logging.WithError(err).Errorf(c, "[tracker] Failed to call Tracker.WorkflowLaunched")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	logging.Infof(c, "[tracker] Successfully tracked workflow launched")
	w.WriteHeader(http.StatusOK)
}

func workerLaunchedHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[tracker] Worker launched queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	wr := &admin.WorkerLaunchedRequest{}
	if err := proto.Unmarshal(body, wr); err != nil {
		logging.WithError(err).Errorf(c, "[tracker] Worker launched queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[tracker] Worker launched request (run ID: %d, Worker: %s)", wr.RunId, wr.Worker)
	if _, err := server.WorkerLaunched(c, wr); err != nil {
		logging.WithError(err).Errorf(c, "[tracker] Failed to call Tracker.WorkerLaunched")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	logging.Infof(c, "[tracker] Successfully tracked worker launched")
	w.WriteHeader(http.StatusOK)
}

func workerDoneHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[tracker] Worker done queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	wr := &admin.WorkerDoneRequest{}
	if err := proto.Unmarshal(body, wr); err != nil {
		logging.WithError(err).Errorf(c, "[tracker] Worker done queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[tracker] Worker done request (run ID: %d, Worker: %s)", wr.RunId, wr.Worker)
	if _, err := server.WorkerDone(c, wr); err != nil {
		logging.WithError(err).Errorf(c, "[tracker] Failed to call Tracker.WorkerDone")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	logging.Infof(c, "[tracker] Successfully tracked worker completion")
	w.WriteHeader(http.StatusOK)
}
