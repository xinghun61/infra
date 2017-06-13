// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"reflect"
	"testing"
	"time"

	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"
)

var baseTime = time.Now()
var serviceIncOne = &backend.ServiceIncident{
	ID:        "idRedOne",
	Open:      false,
	StartTime: baseTime,
	EndTime:   baseTime.AddDate(0, 0, 4),
	Severity:  backend.Severity(0),
}
var chopsIncOne = &dashpb.ChopsIncident{
	Id:        serviceIncOne.ID,
	Open:      serviceIncOne.Open,
	StartTime: serviceIncOne.StartTime.Unix(),
	EndTime:   serviceIncOne.EndTime.Unix(),
	Severity:  dashpb.Severity(int(serviceIncOne.Severity)),
}
var serviceIncTwo = &backend.ServiceIncident{
	ID:        "idYellowTwo",
	Open:      true,
	StartTime: baseTime,
	Severity:  backend.Severity(1),
}
var chopsIncTwo = &dashpb.ChopsIncident{
	Id:        serviceIncTwo.ID,
	Open:      serviceIncTwo.Open,
	StartTime: serviceIncTwo.StartTime.Unix(),
	EndTime:   0,
	Severity:  dashpb.Severity(int(serviceIncTwo.Severity)),
}
var serviceIncidents = []*backend.ServiceIncident{serviceIncOne, serviceIncTwo}
var service = &backend.Service{
	ID:   "serviceID",
	Name: "NormalService",
	SLA:  "www.google.com",
}
var chopsService = dashpb.ChopsService{
	Name:      service.Name,
	Incidents: []*dashpb.ChopsIncident{chopsIncOne, chopsIncTwo},
	Sla:       service.SLA,
}
var emptyService = &backend.Service{
	ID:   "emptyserviceID",
	Name: "EmptyService",
}
var emptyChopsService = dashpb.ChopsService{
	Name:      emptyService.Name,
	Incidents: []*dashpb.ChopsIncident{},
	Sla:       "",
}

func TestConvertToChopsIncident(t *testing.T) {
	testCases := []struct {
		serviceIncident *backend.ServiceIncident
		chopsIncident   *dashpb.ChopsIncident
	}{
		{
			serviceIncident: serviceIncOne,
			chopsIncident:   chopsIncOne,
		},
		{
			serviceIncident: serviceIncTwo,
			chopsIncident:   chopsIncTwo,
		},
	}
	for i, tc := range testCases {
		convertedInc := ConvertToChopsIncident(tc.serviceIncident)
		if !reflect.DeepEqual(tc.chopsIncident, convertedInc) {
			t.Errorf("%d: expected %+v, found %+v", i, tc.chopsIncident, convertedInc)
		}
	}
}

func TestConvertToChopsService(t *testing.T) {
	testCases := []struct {
		service          *backend.Service
		serviceIncidents []*backend.ServiceIncident
		chopsService     dashpb.ChopsService
	}{
		{
			service:          service,
			serviceIncidents: serviceIncidents,
			chopsService:     chopsService,
		},
		{
			service:      emptyService,
			chopsService: emptyChopsService,
		},
	}
	for i, tc := range testCases {
		convertedService := ConvertToChopsService(tc.service, tc.serviceIncidents)
		if !reflect.DeepEqual(tc.chopsService, convertedService) {
			t.Errorf("%d: expected %+v, found %+v", i, tc.chopsService, convertedService)
		}
	}

}
