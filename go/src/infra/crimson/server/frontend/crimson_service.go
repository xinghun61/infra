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

func (s *crimsonService) CreateIPRange(ctx context.Context, req *crimson.IPRange) (*crimson.IPRangeStatus, error) {

	err := crimsondb.InsertIPRange(ctx, req)

	if err != nil {
		return &crimson.IPRangeStatus{}, grpc.Errorf(codes.AlreadyExists, err.Error())
	} else {
		return &crimson.IPRangeStatus{}, nil
	}
}

func (s *crimsonService) ReadIPRange(ctx context.Context, req *crimson.IPRangeQuery) (*crimson.IPRanges, error) {

	rows := crimsondb.SelectIPRange(ctx, req)

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
