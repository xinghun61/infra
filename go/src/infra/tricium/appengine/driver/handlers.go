// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements HTTP handlers to the driver module.
package driver

import (
	"io/ioutil"
	"net/http"

	"github.com/golang/protobuf/proto"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

func triggerHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[driver] Trigger queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	tr := &admin.TriggerRequest{}
	if err := proto.Unmarshal(body, tr); err != nil {
		logging.WithError(err).Errorf(c, "[driver] Trigger queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[driver] Trigger request (run ID: %d, Worker: %s)", tr.RunId, tr.Worker)
	if _, err := server.Trigger(c, tr); err != nil {
		logging.WithError(err).Errorf(c, "[driver] Failed to call Driver.Trigger")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	logging.Infof(c, "[driver] Successfully completed trigger")
	w.WriteHeader(http.StatusOK)
}

func collectHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[driver] Collect queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	cr := &admin.CollectRequest{}
	if err := proto.Unmarshal(body, cr); err != nil {
		logging.WithError(err).Errorf(c, "[driver] Collect queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[driver] Collect request (run ID: %d, Worker: %s)", cr.RunId, cr.Worker)
	if _, err := server.Collect(c, cr); err != nil {
		logging.WithError(err).Errorf(c, "[driver] Failed to call Driver.Collect")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	logging.Infof(c, "[driver] Successfully completed collect")
	w.WriteHeader(http.StatusOK)
}

func notifyHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	logging.Infof(c, "[driver]: Received notify")
	// TODO(emso): Extract actual run ID, isolated input hash, and worker name from notification details.
	runID := int64(1234567)
	inputHash := "abcdefg"
	worker := "Hello_Ubuntu14.04_x86-64"
	// Enqueue collect request
	b, err := proto.Marshal(&admin.CollectRequest{
		RunId:             runID,
		IsolatedInputHash: inputHash,
		Worker:            worker,
	})
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to marshal collect request: %v", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	t := tq.NewPOSTTask("/driver/internal/collect", nil)
	t.Payload = b
	if err := tq.Add(c, common.DriverQueue, t); err != nil {
		logging.WithError(err).Errorf(c, "failed to enqueue collect request: %v", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Infof(c, "[driver] Successfully completed PubSub notify")
	w.WriteHeader(http.StatusOK)
}
