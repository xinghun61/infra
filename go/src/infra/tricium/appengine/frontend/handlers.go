// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package frontend implements HTTP handlers for the frontend (default) module.
package frontend

import (
	"fmt"
	"io/ioutil"
	"net/http"

	"golang.org/x/net/context"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/config"
	"infra/tricium/appengine/common/pipeline"
	"infra/tricium/appengine/common/track"
)

func landingPageHandler(c *router.Context) {
	templates.MustRender(c.Context, c.Writer, "pages/index.html", map[string]interface{}{
		"StatusMsg": "This service is under construction.",
	})
}

func resultsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	r, err := requests(c, config.LuciConfigServer)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to retrieve requests")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	templates.MustRender(c, w, "pages/results.html", map[string]interface{}{
		"Requests": r,
	})
}

// requests returns list of workflow runs for projects readable to the current user.
func requests(c context.Context, cp config.ProviderAPI) ([]*track.AnalyzeRequest, error) {
	// TODO(emso): This only lists the last 20 requests, when the UI is ready improve to list more.
	var requests []*track.AnalyzeRequest
	q := ds.NewQuery("AnalyzeRequest").Order("-Received").Limit(20)
	if err := ds.GetAll(c, q, &requests); err != nil {
		logging.WithError(err).Errorf(c, "failed to get AnalyzeRequest entities: %v", err)
		return nil, err
	}
	// Only include readable Analyze requests.
	checked := map[string]bool{}
	var rs []*track.AnalyzeRequest
	for _, r := range requests {
		if _, ok := checked[r.Project]; !ok {
			pc, err := cp.GetProjectConfig(c, r.Project)
			if err != nil {
				logging.WithError(err).Errorf(c, "failed to get config for project %s: %v", r.Project, err)
				return nil, err
			}
			checked[r.Project], err = tricium.CanRead(c, pc)
			if err != nil {
				logging.WithError(err).Errorf(c, "failed to check read access %s: %v", r.Project, err)
				return nil, err
			}
		}
		if checked[r.Project] {
			rs = append(rs, r)
		}
	}
	return rs, nil
}

func analyzeFormHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	// TODO(emso): With a switch to Polymer this handler can be replaced with a direct
	// call to the pRPC server via Javascript fetch.
	sr, err := parseRequestForm(r)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to parse analyze request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	res, err := server.Analyze(c, &tricium.AnalyzeRequest{
		Project: sr.Project,
		GitRef:  sr.GitRef,
		Paths:   sr.Paths,
	})
	// TODO(emso): Sort out the returned error code to distinguish retriable errors
	// from fatal errors. For instance, grpc.Code(err) equal to codes.InvalidArgument is fatal, while
	// codes.Internal is not.
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to call Tricium.Analyze RPC")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	logging.Infof(c, "Analyzer handler successfully completed, run ID: %s", res.RunId)
	templates.MustRender(c, w, "pages/index.html", map[string]interface{}{
		"StatusMsg": fmt.Sprintf("Analysis request sent, run ID: %s", res.RunId),
	})
	w.WriteHeader(http.StatusOK)
}

func parseRequestForm(r *http.Request) (*pipeline.ServiceRequest, error) {
	r.ParseForm()
	project := r.FormValue("Project")
	ref := r.FormValue("GitRef")
	paths := []string{}
	for _, p := range r.Form["Path[]"] {
		paths = append(paths, p)
	}
	if project == "" || ref == "" || len(paths) == 0 {
		return nil, fmt.Errorf("Missing required information, project: %s, ref: %s, paths: %v", project, ref, paths)
	}
	return &pipeline.ServiceRequest{
		Project: project,
		GitRef:  ref,
		Paths:   paths,
	}, nil
}

// analyzeHandler calls Tricium.Analyze for entries in the analyze queue.
//
// This queue is intended as a service extension point for modules
// running within the Tricium GAE app. For instance, the Gerrit poller.
// TODO(emso): Figure out if this queue is needed.
// TODO(emso): Figure out if/where WrapTransient should be used for errors.
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
