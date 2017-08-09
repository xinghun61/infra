// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"
	"time"

	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"
)

// TemplateService bundles a backend.Service with its backend.ServiceIncident children.
type TemplateService struct {
	Service   backend.Service
	Incidents []backend.ServiceIncident
}

// ConvertToChopsIncident takes a backend.ServiceIncident struct and returns a dashpb.ChopsIncident equivalent.
func ConvertToChopsIncident(serviceIncident *backend.ServiceIncident) *dashpb.ChopsIncident {
	chopsIncident := dashpb.ChopsIncident{
		Id:        serviceIncident.ID,
		Open:      serviceIncident.Open,
		StartTime: serviceIncident.StartTime.Unix(),
		Severity:  dashpb.Severity(int(serviceIncident.Severity)),
	}
	if !chopsIncident.Open {
		chopsIncident.EndTime = serviceIncident.EndTime.Unix()
	}
	return &chopsIncident
}

// ConvertToChopsService takes a backedn Service and its Incidents struct and returns a dashpb.ChopsService equivalent.
func ConvertToChopsService(service *backend.Service, serviceIncidents []backend.ServiceIncident) *dashpb.ChopsService {
	// Convert service_incidents to ChopsIncidents.
	chopsIncidents := make([]*dashpb.ChopsIncident, len(serviceIncidents))
	for i, incident := range serviceIncidents {
		chopsIncidents[i] = ConvertToChopsIncident(&incident)
	}

	chopsService := &dashpb.ChopsService{
		Name:      service.Name,
		Incidents: chopsIncidents,
		Sla:       service.SLA,
	}
	return chopsService
}

func createServicesPageData(c context.Context, after time.Time, before time.Time) (sla []TemplateService, nonSLA []TemplateService, err error) {
	services, e := backend.GetAllServices(c)
	if e != nil {
		logging.Errorf(c, "error getting Service entities %s", e)
		return nil, nil, e
	}
	closedQueryOpts := &backend.QueryOptions{
		After:  after,
		Before: before,
		Status: backend.IncidentStatusClosed,
	}
	openQueryOpts := &backend.QueryOptions{
		Status: backend.IncidentStatusOpen,
	}

	for _, service := range services {
		closedIncidents, e := backend.GetServiceIncidents(c, service.ID, closedQueryOpts)
		if err != nil {
			logging.Errorf(c, "error getting ServiceIncident entities %s", e)
			return nil, nil, e
		}
		openIncidents, e := backend.GetServiceIncidents(c, service.ID, openQueryOpts)
		if err != nil {
			logging.Errorf(c, "error getting ServiceIncident entities %s", e)
			return nil, nil, e
		}
		templateService := TemplateService{service, append(openIncidents, closedIncidents...)}

		if service.SLA == "" {
			nonSLA = append(nonSLA, templateService)
		} else {
			sla = append(sla, templateService)
		}
	}
	return
}
