// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"io/ioutil"
	"net/http"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common/config"
)

type gerritReporter struct{}

var reporter = &gerritReporter{}

// pollHandler triggers poll requests for each project for this service.
//
// This handler should be called periodically by a cron job.
func pollHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	if err := poll(c, config.LuciConfigServer); err != nil {
		logging.WithError(err).Errorf(c, "failed to poll")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Debugf(c, "[gerrit] Successfully completed poll")
	w.WriteHeader(http.StatusOK)
}

// pollProjectHandler polls Gerrit for each applicable repo for one project.
//
// This handler should handle tasks on a push task queue.
func pollProjectHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	logging.Debugf(c, "[gerrit] Received request from poll project queue.")
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[gerrit] Failed to read request body.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	request := &admin.PollProjectRequest{}
	if err = proto.Unmarshal(body, request); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit] Failed to unmarshal request.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	if err = pollProject(c, request.Project, GerritServer, config.LuciConfigServer); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit] failed to poll project")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Debugf(c, "[gerrit] Successfully completed poll project")
	w.WriteHeader(http.StatusOK)
}

func resultsHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[gerrit] Results queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	rr := &admin.ReportResultsRequest{}
	if err := proto.Unmarshal(body, rr); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit] Results queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Fields{
		"run ID":   rr.RunId,
		"analyzer": rr.Analyzer,
	}.Infof(c, "[gerrit] Report results request received")
	if _, err := reporter.ReportResults(c, rr); err != nil {
		logging.WithError(err).Errorf(c, "[gerrit] Failed to call Gerrit.ReportResults")
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
