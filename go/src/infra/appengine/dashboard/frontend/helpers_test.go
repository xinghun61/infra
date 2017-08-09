// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"reflect"
	"testing"
	"time"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"golang.org/x/net/context"

	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"
)

var baseTime = time.Date(2017, time.April, 11, 23, 0, 0, 0, time.UTC)
var serviceIncOne = backend.ServiceIncident{
	ID:        "idRedOne",
	Open:      false,
	StartTime: baseTime.AddDate(0, 0, -4),
	EndTime:   baseTime.AddDate(0, 0, -3),
	Severity:  backend.SeverityRed,
}
var chopsIncOne = &dashpb.ChopsIncident{
	Id:        serviceIncOne.ID,
	Open:      serviceIncOne.Open,
	StartTime: serviceIncOne.StartTime.Unix(),
	EndTime:   serviceIncOne.EndTime.Unix(),
	Severity:  dashpb.Severity(int(serviceIncOne.Severity)),
}
var serviceIncTwo = backend.ServiceIncident{
	ID:        "idYellowTwo",
	Open:      true,
	StartTime: baseTime,
	Severity:  backend.SeverityYellow,
}
var chopsIncTwo = &dashpb.ChopsIncident{
	Id:        serviceIncTwo.ID,
	Open:      serviceIncTwo.Open,
	StartTime: serviceIncTwo.StartTime.Unix(),
	EndTime:   0,
	Severity:  dashpb.Severity(int(serviceIncTwo.Severity)),
}
var serviceIncidents = []backend.ServiceIncident{serviceIncOne, serviceIncTwo}
var service = backend.Service{
	ID:   "serviceID",
	Name: "NormalService",
	SLA:  "www.google.com",
}
var chopsService = dashpb.ChopsService{
	Name:      service.Name,
	Incidents: []*dashpb.ChopsIncident{chopsIncOne, chopsIncTwo},
	Sla:       service.SLA,
}
var emptyService = backend.Service{
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
			serviceIncident: &serviceIncOne,
			chopsIncident:   chopsIncOne,
		},
		{
			serviceIncident: &serviceIncTwo,
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
		serviceIncidents []backend.ServiceIncident
		chopsService     *dashpb.ChopsService
	}{
		{
			service:          &service,
			serviceIncidents: serviceIncidents,
			chopsService:     &chopsService,
		},
		{
			service:      &emptyService,
			chopsService: &emptyChopsService,
		},
	}
	for i, tc := range testCases {
		convertedService := ConvertToChopsService(tc.service, tc.serviceIncidents)
		if !reflect.DeepEqual(tc.chopsService, convertedService) {
			t.Errorf("%d: expected %+v, found %+v", i, tc.chopsService, convertedService)
		}
	}

}

var (
	incidentStartIdx = datastore.IndexDefinition{
		Kind:     "ServiceIncident",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{
				Property: "Open",
			},
			{
				Property: "StartTime",
			},
		},
	}
	incidentIneqEndIdx = datastore.IndexDefinition{
		Kind:     "ServiceIncident",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{
				Property: "Open",
			},
			{
				Property: "EndTime",
			},
		},
	}
	indexes = []*datastore.IndexDefinition{&incidentStartIdx, &incidentIneqEndIdx}
)

func newTestContext() context.Context {
	ctx := gaetesting.TestingContext()
	testing := datastore.GetTestable(ctx)
	testing.Consistent(true)
	testing.AddIndexes(indexes...)
	return ctx
}

func TestCreateServicesPageData(t *testing.T) {
	ctx := newTestContext()
	datastore.Put(ctx, &service)
	testOpenInc := serviceIncTwo
	testOpenInc.ServiceKey = datastore.NewKey(ctx, "Service", service.ID, 0, nil)
	err := datastore.Put(ctx, &testOpenInc)
	if err != nil {
		t.Errorf("did not expect error, found %v", err)
	}

	testCloseInc := serviceIncOne
	testCloseInc.ServiceKey = datastore.NewKey(ctx, "Service", service.ID, 0, nil)
	err = datastore.Put(ctx, &testCloseInc)
	if err != nil {
		t.Errorf("did not expect error, found %v", err)
	}

	datastore.Put(ctx, &emptyService)

	wantSLA := []TemplateService{
		{service, []backend.ServiceIncident{testOpenInc, testCloseInc}},
	}
	wantNonSLA := []TemplateService{
		{emptyService, []backend.ServiceIncident{}},
	}
	sla, nonSLA, err := createServicesPageData(ctx, baseTime.AddDate(0, 0, -5), baseTime.AddDate(0, 0, -1))
	if err != nil {
		t.Errorf("did not expect error, found %v", err)
	}
	if !reflect.DeepEqual(sla, wantSLA) {
		t.Errorf("found %v \n want %v", sla, wantSLA)
	}
	if !reflect.DeepEqual(nonSLA, wantNonSLA) {
		t.Errorf("found %v want %v", nonSLA, wantNonSLA)
	}
}
