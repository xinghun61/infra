// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	dashpb "infra/appengine/dashboard/api/dashboard"

	"golang.org/x/net/context"
)

type dashboardService struct{}

func (s *dashboardService) UpdateOpenIncidents(ctx context.Context, req *dashpb.UpdateOpenIncidentsRequest) (*dashpb.UpdateOpenIncidentsResponse, error) {
	// Use data in req to call backend services to update entities in datastore.
	return nil, nil
}
