// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"github.com/luci/luci-go/server/auth"
	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/crimson/proto"
)

type greeterService struct{}

func (s *greeterService) SayHello(c context.Context, req *crimson.HelloRequest) (*crimson.HelloReply, error) {
	if req.Name == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "Name unspecified")
	}

	return &crimson.HelloReply{
		Message: "Hello " + req.Name + " ; " + auth.CurrentIdentity(c).Email(),
	}, nil
}
