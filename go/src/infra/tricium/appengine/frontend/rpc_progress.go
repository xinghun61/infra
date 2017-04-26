// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"strconv"
	"strings"

	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

// Progress implements Tricium.Progress.
func (r *TriciumServer) Progress(c context.Context, req *tricium.ProgressRequest) (*tricium.ProgressResponse, error) {
	if req.RunId == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	runID, err := strconv.ParseInt(req.RunId, 10, 64)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to parse run ID: %s", req.RunId)
		return nil, grpc.Errorf(codes.InvalidArgument, "invalid run ID")
	}
	runState, analyzerProgress, err := progress(c, runID)
	if err != nil {
		logging.WithError(err).Errorf(c, "progress failed: %v, run ID: %d", err, runID)
		return nil, grpc.Errorf(codes.Internal, "failed to execute progress request")
	}
	logging.Infof(c, "[frontend] Analyzer progress: %v", analyzerProgress)
	return &tricium.ProgressResponse{
		State:            runState,
		AnalyzerProgress: analyzerProgress,
	}, nil
}

func progress(c context.Context, runID int64) (tricium.State, []*tricium.AnalyzerProgress, error) {
	run := &track.Run{ID: runID}
	if err := ds.Get(c, run); err != nil {
		return tricium.State_PENDING, nil, fmt.Errorf("failed to read run entry: %v", err)
	}
	runKey := ds.NewKey(c, "Run", "", runID, nil)
	var analyzers []*track.AnalyzerInvocation
	q := ds.NewQuery("AnalyzerInvocation").Ancestor(runKey)
	if err := ds.GetAll(c, q, &analyzers); err != nil {
		return tricium.State_PENDING, nil, fmt.Errorf("failed to read analyzer invocations: %v", err)
	}
	var workers []*track.WorkerInvocation
	q = ds.NewQuery("WorkerInvocation").Ancestor(runKey)
	if err := ds.GetAll(c, q, &workers); err != nil {
		return tricium.State_PENDING, nil, fmt.Errorf("failed to read worker invocations: %v", err)
	}
	res := []*tricium.AnalyzerProgress{}
	for _, w := range workers {
		res = append(res, &tricium.AnalyzerProgress{
			Analyzer:          extractAnalyzerName(w.Name),
			Platform:          w.Platform,
			State:             w.State,
			SwarmingTaskId:    fmt.Sprintf("%s/task?id=%s", w.SwarmingURL, w.TaskID),
			NumResultComments: int32(w.NumResultComments),
		})
	}
	return run.State, res, nil
}

func extractAnalyzerName(worker string) string {
	parts := strings.SplitN(worker, "_", 2)
	if len(parts) == 0 {
		return worker
	}
	return parts[0]
}
