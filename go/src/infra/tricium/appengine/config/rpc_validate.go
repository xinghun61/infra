// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common/config"
)

// ConfigServer represents the Tricium pRPC Config server.
type configServer struct{}

var server = &configServer{}

// Validate validates a project config.
func (*configServer) Validate(c context.Context, req *admin.ValidateRequest) (*admin.ValidateResponse, error) {
	if req.ProjectConfig == nil {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing project config")
	}
	sc := req.ServiceConfig
	if sc == nil {
		var err error
		if sc, err = config.LuciConfigProvider.GetServiceConfig(c); err != nil {
			logging.WithError(err).Errorf(c, "failed to get service config: %v", err)
			return nil, grpc.Errorf(codes.InvalidArgument, "failed to get service config")
		}
	}
	pc, err := config.Validate(sc, req.ProjectConfig)
	if err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to validate config")
	}
	return &admin.ValidateResponse{ValidatedConfig: pc}, nil
}
