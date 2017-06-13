// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"
)

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
func ConvertToChopsService(service *backend.Service, serviceIncidents []*backend.ServiceIncident) dashpb.ChopsService {
	// Convert service_incidents to ChopsIncidents.
	chopsIncidents := make([]*dashpb.ChopsIncident, len(serviceIncidents))
	for i, incident := range serviceIncidents {
		chopsIncidents[i] = ConvertToChopsIncident(incident)
	}

	chopsService := dashpb.ChopsService{
		Name:      service.Name,
		Incidents: chopsIncidents,
		Sla:       service.SLA,
	}
	return chopsService
}
