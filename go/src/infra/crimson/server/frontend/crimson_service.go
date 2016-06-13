// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"golang.org/x/net/context"

	"infra/crimson/proto"
	"infra/crimson/server/crimsondb"
)

type crimsonService struct{}

func (s *crimsonService) CreateIPRange(ctx context.Context, req *crimson.IPRange) (*crimson.IPRangeStatus, error) {

	row := crimsondb.IPRangeRow{
		Site:    req.Site,
		Vlan:    req.Vlan,
		StartIp: req.StartIp,
		EndIp:   req.EndIp,
	}

	crimsondb.InsertIPRangeRows(ctx, []crimsondb.IPRangeRow{row})

	return &crimson.IPRangeStatus{
		Error: "no error",
	}, nil
}

func (s *crimsonService) ReadIPRange(ctx context.Context, req *crimson.IPRangeQuery) (*crimson.IPRanges, error) {

	rows := crimsondb.SelectIPRange(ctx, req.Vlan, req.Site)

	ret := crimson.IPRanges{}
	for _, row := range rows {
		ret.Ranges = append(
			ret.Ranges,
			&crimson.IPRange{
				Site:    row.Site,
				Vlan:    row.Vlan,
				StartIp: row.StartIp,
				EndIp:   row.EndIp,
			})
	}
	return &ret, nil
}
