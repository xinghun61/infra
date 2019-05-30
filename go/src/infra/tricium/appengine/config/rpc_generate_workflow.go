// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common/config"
)

// ConfigServer represents the Tricium pRPC Config server.
type configServer struct{}

var server = &configServer{}

func (*configServer) GenerateWorkflow(c context.Context, req *admin.GenerateWorkflowRequest) (*admin.GenerateWorkflowResponse, error) {
	if req.Project == "" {
		return nil, status.Errorf(codes.InvalidArgument, "missing project name")
	}
	pc, err := config.LuciConfigServer.GetProjectConfig(c, req.Project)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to get project config: %v", err)
	}
	sc, err := config.LuciConfigServer.GetServiceConfig(c)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to get service config: %v", err)
	}
	wf, err := config.Generate(sc, pc, req.Files, "", "")
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to validate config: %v", err)
	}
	return &admin.GenerateWorkflowResponse{Workflow: wf}, nil
}
