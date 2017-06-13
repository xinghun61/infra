// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"golang.org/x/net/context"
)

type dashboardService struct{}

func (s *dashboardService) UpdateOpenIncidents(ctx context.Context, req *dashpb.UpdateOpenIncidentsRequest) (*dashpb.UpdateOpenIncidentsResponse, error) {
	if req.ChopsService == nil {
		return nil, grpc.Errorf(codes.InvalidArgument, "chopsService field was empty")
	}
	serviceName := req.ChopsService.Name
	if serviceName == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "name field in ChopsService was empty")
	}

	incidentsByID := make(map[string]dashpb.ChopsIncident, len(req.ChopsService.Incidents))
	for _, incident := range req.ChopsService.Incidents {
		incidentsByID[incident.Id] = *incident
	}

	dsIncidents, err := backend.GetServiceIncidents(ctx, serviceName, &backend.QueryOptions{Status: backend.IncidentStatusOpen})
	if err != nil {
		return nil, grpc.Errorf(codes.Internal, "error getting ServiceIncidents from datastore - %s", err)
	}
	for _, dsIncident := range dsIncidents {
		id := dsIncident.ID
		if _, exists := incidentsByID[id]; !exists { // Incident no longer open
			backend.CloseIncident(ctx, id, serviceName)
		} else {
			delete(incidentsByID, id)
		}
	}

	// Add remaining new incidents to datastore
	for id, inc := range incidentsByID {
		err := backend.AddIncident(ctx, id, serviceName, backend.Severity(int(inc.Severity)))
		if err != nil {
			return nil, grpc.Errorf(codes.Internal, "error storing new Incident to datastore - %s", err)
		}
	}

	return &dashpb.UpdateOpenIncidentsResponse{
		OpenIncidents: req.ChopsService.Incidents,
	}, nil
}
