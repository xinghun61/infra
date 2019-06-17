// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io/ioutil"
	"net/http"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	admin "infra/tricium/api/admin/v1"
)

var tracker = &trackerServer{}

func workflowLaunchedHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to read request body.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	wr := &admin.WorkflowLaunchedRequest{}
	if err := proto.Unmarshal(body, wr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to unmarshal request.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Fields{
		"runID": wr.RunId,
	}.Infof(c, "Request received.")
	if _, err := tracker.WorkflowLaunched(c, wr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to call WorkflowLaunched.")
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

func workerLaunchedHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to read request body.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	wr := &admin.WorkerLaunchedRequest{}
	if err := proto.Unmarshal(body, wr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to unmarshal request.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Fields{
		"runID":  wr.RunId,
		"worker": wr.Worker,
	}.Infof(c, "Request received.")
	if _, err := tracker.WorkerLaunched(c, wr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to call WorkerLaunched.")
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

func workerDoneHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to read request body.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	wr := &admin.WorkerDoneRequest{}
	if err := proto.Unmarshal(body, wr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to unmarshal request.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Fields{
		"runID":  wr.RunId,
		"worker": wr.Worker,
	}.Infof(c, "Request received.")
	if _, err := tracker.WorkerDone(c, wr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to call WorkerDone.")
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
