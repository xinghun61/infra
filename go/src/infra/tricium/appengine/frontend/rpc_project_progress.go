// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"strconv"

	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/config"
	"infra/tricium/appengine/common/track"
)

// ProjectProgress implements Tricium.ProjectProgress.
func (r *TriciumServer) ProjectProgress(c context.Context, req *tricium.ProjectProgressRequest) (*tricium.ProjectProgressResponse, error) {
	project, err := validateProjectProgressRequest(c, req)
	if err != nil {
		return nil, err
	}
	runProgress, errCode, err := projectProgress(c, project, config.LuciConfigServer)
	if err != nil {
		logging.WithError(err).Errorf(c, "project progress failed: %v, project: %s", err, project)
		return nil, grpc.Errorf(errCode, "failed to execute progress request")
	}
	logging.Infof(c, "[frontend] Project progress: %v", runProgress)
	return &tricium.ProjectProgressResponse{
		RunProgress: runProgress,
	}, nil
}

func validateProjectProgressRequest(c context.Context, req *tricium.ProjectProgressRequest) (string, error) {
	if req.Project == "" {
		return "", grpc.Errorf(codes.InvalidArgument, "missing Tricium project")
	}
	return req.Project, nil
}

func projectProgress(c context.Context, project string, cp config.ProviderAPI) ([]*tricium.RunProgress, codes.Code, error) {
	sc, err := cp.GetServiceConfig(c)
	if err != nil {
		return nil, codes.Internal, fmt.Errorf("failed to get service config: %v", err)
	}
	pd := tricium.LookupProjectDetails(sc, project)
	if pd == nil {
		return nil, codes.InvalidArgument, fmt.Errorf("unknown project")
	}
	var runProgress []*tricium.RunProgress
	var requests []*track.AnalyzeRequest
	if err := ds.GetAll(c, ds.NewQuery("AnalyzeRequest").Eq("Project", project), &requests); err != nil {
		return nil, codes.Internal, fmt.Errorf("failed to retrieve AnalyzeRequest entities: %v", err)
	}
	for _, r := range requests {
		key := ds.KeyForObj(c, r)
		res := &track.AnalyzeRequestResult{ID: 1, Parent: key}
		if err := ds.Get(c, res); err != nil {
			return nil, codes.Internal, fmt.Errorf("failed to retrieve AnalyzerRequestResult: %v", err)
		}
		var functionResults []*track.FunctionRunResult
		if err := ds.GetAll(c, ds.NewQuery("FunctionRunResult").Ancestor(key), &functionResults); err != nil {
			return nil, codes.Internal, fmt.Errorf("failed to retrieve FunctionRunResult: %v", err)
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
	return runProgress, codes.OK, nil
}
