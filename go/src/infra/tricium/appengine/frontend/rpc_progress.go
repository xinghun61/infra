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

// Progress implements Tricium.Progress.
func (r *TriciumServer) Progress(c context.Context, req *tricium.ProgressRequest) (*tricium.ProgressResponse, error) {
	if req.RunId == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	ap, err := progress(c, req)
	if err != nil {
		logging.WithError(err).Errorf(c, "progress failed: %v", err)
		return nil, grpc.Errorf(codes.Internal, "failed to execute progress request")
	}
	logging.Infof(c, "[frontend] Analyzer progress: %v", ap)
	return &tricium.ProgressResponse{AnalyzerProgress: ap}, nil
}

func progress(c context.Context, req *tricium.ProgressRequest) ([]*tricium.AnalyzerProgress, error) {
	// TODO(emso): Implement
	return []*tricium.AnalyzerProgress{}, nil
}
