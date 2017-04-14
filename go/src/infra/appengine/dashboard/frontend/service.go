// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"fmt"
	dashpb "infra/appengine/dashboard/api/dashboard"

	"golang.org/x/net/context"
)

type dashboardService struct{}

func (s *dashboardService) UpdateOpenIncidents(ctx context.Context, req *dashpb.UpdateOpenIncidentsRequest) (*dashpb.UpdateOpenIncidentsResponse, error) {
	if req.ChopsService == nil {
		return nil, fmt.Errorf("ChopsService field in request %v was empty", req)
	}
	serviceName := req.ChopsService.Name
	if serviceName == "" {
		return nil, fmt.Errorf("Name field in ChopsService %v was empty", req.ChopsService)
	}

	// TODO(jojwang): Update dsIncidents = backend.GetServiceIncidents to have optional argument to specify we only want open Incidents.
	// for each dsIncident: if dsIncident not in chopsService.Incidents: CloseIncident(dsIncident)
	// for each chopsService.Incidents: if chopsService.Incidents not in dsIncidents: backend.AddIncident(chopsService.Incident)

	return &dashpb.UpdateOpenIncidentsResponse{
		OpenIncidents: req.ChopsService.Incidents,
	}, nil

}
