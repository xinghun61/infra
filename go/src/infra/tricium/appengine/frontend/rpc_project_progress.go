// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"strconv"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/grpcutil"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/config"
	"infra/tricium/appengine/common/track"
)

// ProjectProgress implements Tricium.ProjectProgress.
func (r *TriciumServer) ProjectProgress(c context.Context, req *tricium.ProjectProgressRequest) (res *tricium.ProjectProgressResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	project, err := validateProjectProgressRequest(c, req)
	if err != nil {
		return nil, err
	}
	logging.Fields{
		"project": project,
	}.Infof(c, "Request validated.")
	runProgress, err := projectProgress(c, project, config.LuciConfigServer)
	if err != nil {
		return nil, err
	}
	return &tricium.ProjectProgressResponse{
		RunProgress: runProgress,
	}, nil
}

func validateProjectProgressRequest(c context.Context, req *tricium.ProjectProgressRequest) (string, error) {
	if req.Project == "" {
		return "", errors.New("missing Tricium project", grpcutil.InvalidArgumentTag)
	}
	return req.Project, nil
}

func projectProgress(c context.Context, project string, cp config.ProviderAPI) ([]*tricium.RunProgress, error) {
	var runProgress []*tricium.RunProgress
	var requests []*track.AnalyzeRequest
	if err := ds.GetAll(c, ds.NewQuery("AnalyzeRequest").Eq("Project", project), &requests); err != nil {
		return nil, errors.Annotate(err, "failed to get AnalyzeRequests").
			Tag(grpcutil.InternalTag).Err()
	}
	for _, r := range requests {
		key := ds.KeyForObj(c, r)
		res := &track.AnalyzeRequestResult{ID: 1, Parent: key}
		if err := ds.Get(c, res); err != nil {
			return nil, errors.Annotate(err, "failed to get AnalyzeRequestResult").
				Tag(grpcutil.InternalTag).Err()
		}
		var functionResults []*track.FunctionRunResult
		if err := ds.GetAll(c, ds.NewQuery("FunctionRunResult").Ancestor(key), &functionResults); err != nil {
			return nil, errors.Annotate(err, "failed to get FunctionRunResult").
				Tag(grpcutil.InternalTag).Err()
		}
		numComments := 0
		for _, ar := range functionResults {
			numComments += ar.NumComments
		}
		runProgress = append(runProgress, &tricium.RunProgress{
			RunId:       strconv.FormatInt(r.ID, 10),
			State:       res.State,
			NumComments: int32(numComments),
		})
	}
	return runProgress, nil
}
