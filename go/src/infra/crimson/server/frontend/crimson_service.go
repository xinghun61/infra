// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/crimson/proto"
	"infra/crimson/server/crimsondb"
)

type crimsonService struct{}

// userErrorToGRPCError turns UserError into grpc.Error and pass the
// other types through.
func userErrorToGRPCError(err error) error {
	if err == nil {
		return err
	}
	if userError, ok := err.(*crimsondb.UserError); ok {
		return grpc.Errorf(codes.Code(userError.Code()), userError.Error())
	}
	return err
}

func (s *crimsonService) CreateIPRange(ctx context.Context, req *crimson.IPRange) (*crimson.IPRangeStatus, error) {
	// TODO(pgervais): uncouple InsertIpRange and infra/crimson/proto
	// Create a separate proto file with grpc-independent data structures and use
	// them here.
	err := crimsondb.InsertIPRange(ctx, req)
	return &crimson.IPRangeStatus{}, userErrorToGRPCError(err)
}

func (s *crimsonService) ReadIPRange(ctx context.Context, req *crimson.IPRangeQuery) (*crimson.IPRanges, error) {

	rows, err := crimsondb.SelectIPRange(ctx, req)

	if err != nil {
		return nil, userErrorToGRPCError(err)
	}
	ret := crimson.IPRanges{}

	for _, row := range rows {
		ret.Ranges = append(
			ret.Ranges,
			&crimson.IPRange{
				Site:    row.Site,
				Vlan:    row.Vlan,
				StartIp: row.StartIP,
				EndIp:   row.EndIP,
			})
	}
	return &ret, nil
}

func (s *crimsonService) CreateHost(ctx context.Context, req *crimson.HostList) (*crimson.HostStatus, error) {
	err := crimsondb.InsertHost(ctx, req)
	return &crimson.HostStatus{}, userErrorToGRPCError(err)
}

func (s *crimsonService) ReadHost(ctx context.Context, req *crimson.HostQuery) (*crimson.HostList, error) {
	rows, err := crimsondb.SelectHost(ctx, req)

	if err == nil {
		return rows, nil
	}
	return nil, userErrorToGRPCError(err)
}

func (s *crimsonService) DeleteHost(ctx context.Context, req *crimson.HostDeleteList) (*crimson.HostStatus, error) {
	err := crimsondb.DeleteHost(ctx, req)
	return &crimson.HostStatus{}, userErrorToGRPCError(err)
}
