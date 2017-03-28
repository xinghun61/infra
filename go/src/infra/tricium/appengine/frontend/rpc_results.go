// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/v1"
)

// Results processes one results request to Tricium.
func (r *TriciumServer) Results(c context.Context, req *tricium.ResultsRequest) (*tricium.ResultsResponse, error) {
	if req.RunId == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	results, isMerged, err := results(c, req)
	if err != nil {
		logging.WithError(err).Errorf(c, "results failed: %v", err)
		return nil, grpc.Errorf(codes.Internal, "failed to execute results request")
	}
	logging.Infof(c, "[frontend] Results: %v", results)
	return &tricium.ResultsResponse{Results: results, IsMerged: isMerged}, nil
}

func results(c context.Context, req *tricium.ResultsRequest) (*tricium.Data_Results, bool, error) {
	// TODO(emso): Implement
	return &tricium.Data_Results{}, false, nil
}
