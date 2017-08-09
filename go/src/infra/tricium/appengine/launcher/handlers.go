// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package launcher implements HTTP handlers for the launcher module.
package launcher

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

func launchHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[launcher] Queue handler failed to read request body")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	lr := &admin.LaunchRequest{}
	if err := proto.Unmarshal(body, lr); err != nil {
		logging.WithError(err).Errorf(c, "[launcher] Queue handler failed to unmarshal launch request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	if _, err := server.Launch(c, lr); err != nil {
		logging.WithError(err).Errorf(c, "[launcher] Failed to call Launcher.Launch")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	logging.Infof(c, "[launcher] Successfully completed")
	w.WriteHeader(http.StatusOK)
}
