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

// Validate validates a project config.
func (*configServer) Validate(c context.Context, req *admin.ValidateRequest) (*admin.ValidateResponse, error) {
	if req.ProjectConfig == nil {
		return nil, status.Errorf(codes.InvalidArgument, "missing project config")
	}
	sc := req.ServiceConfig
	if sc == nil {
		var err error
		if sc, err = config.LuciConfigServer.GetServiceConfig(c); err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "failed to get service config: %v", err)
		}
	}
	pc, err := config.Validate(sc, req.ProjectConfig)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to validate config: %v", err)
	}
	return &admin.ValidateResponse{ValidatedConfig: pc}, nil
}
