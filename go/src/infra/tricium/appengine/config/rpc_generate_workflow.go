// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common/config"
)

func (*configServer) GenerateWorkflow(c context.Context, req *admin.GenerateWorkflowRequest) (*admin.GenerateWorkflowResponse, error) {
	if req.Project == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing project name")
	}
	pc, err := config.LuciConfigServer.GetProjectConfig(c, req.Project)
	if err != nil {
		return nil, grpc.Errorf(codes.InvalidArgument, "failed to get project config: %v", err)
	}
	sc, err := config.LuciConfigServer.GetServiceConfig(c)
	if err != nil {
		return nil, grpc.Errorf(codes.InvalidArgument, "failed to get service config: %v", err)
	}
	wf, err := config.Generate(sc, pc, req.Files)
	if err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to validate config: %v", err)
	}
	return &admin.GenerateWorkflowResponse{Workflow: wf}, nil
}
