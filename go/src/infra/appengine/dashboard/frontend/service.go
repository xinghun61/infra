// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"golang.org/x/net/context"
)

type dashboardService struct{}

func (s *dashboardService) UpdateOpenIncidents(ctx context.Context, req *dashpb.UpdateOpenIncidentsRequest) (*dashpb.UpdateOpenIncidentsResponse, error) {
	if req.ChopsService == nil {
		return nil, status.Error(codes.InvalidArgument, "ChopsService field was empty")
	}
	serviceName := req.ChopsService.Name
	if serviceName == "" {
		return nil, status.Error(codes.InvalidArgument, "name field in ChopsService was empty")
	}

	incidentsByID := make(map[string]dashpb.ChopsIncident, len(req.ChopsService.Incidents))
	for _, incident := range req.ChopsService.Incidents {
		incidentsByID[incident.Id] = *incident
	}

	dsIncidents, err := backend.GetServiceIncidents(ctx, serviceName, &backend.QueryOptions{Status: backend.IncidentStatusOpen})
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error getting ServiceIncidents from datastore - %s", err)
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
			return nil, status.Errorf(codes.Internal, "error storing new Incident to datastore - %s", err)
		}
	}

	return &dashpb.UpdateOpenIncidentsResponse{
		OpenIncidents: req.ChopsService.Incidents,
	}, nil
}

func (s *dashboardService) GetAllServicesData(ctx context.Context, req *dashpb.GetAllServicesDataRequest) (*dashpb.GetAllServicesDataResponse, error) {
	// Parse UptoTime field
	var lastDate time.Time
	if req.UptoTime == 0 {
		lastDate = time.Now()
	} else {
		lastDate = time.Unix(req.UptoTime, 0)
	}
	// Lower limit of date span is pushed back (from -6 to -7) for timezones that are behind
	// UTC and may have a current time that is still one calendar day behind the UTC
	// day. Incidents from the query that are too far back are filtered out
	// in the front end when all Dates are local.
	firstDate := lastDate.AddDate(0, 0, -7)

	slaTemplateService, nonSLATemplateService, err := createServicesPageData(ctx, firstDate, lastDate)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error collecting data from datastore - %s", err)
	}
	chopsServices := make([]*dashpb.ChopsService, len(slaTemplateService))
	for i, templateService := range slaTemplateService {
		chopsServices[i] = ConvertToChopsService(ctx, &templateService.Service, templateService.Incidents)
	}

	nonSLAChopsServices := make([]*dashpb.ChopsService, len(nonSLATemplateService))
	for i, templateService := range nonSLATemplateService {
		nonSLAChopsServices[i] = ConvertToChopsService(ctx, &templateService.Service, templateService.Incidents)
	}

	return &dashpb.GetAllServicesDataResponse{
		Services:       chopsServices,
		NonslaServices: nonSLAChopsServices,
	}, nil
}
