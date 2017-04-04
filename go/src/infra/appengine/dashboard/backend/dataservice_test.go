// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"reflect"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/appengine/gaetesting"
)

var (
	serviceIdx = datastore.IndexDefinition{
		Kind:     "Service",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{
				Property:   "Name",
				Descending: true,
			},
		},
	}

	incidentIdx = datastore.IndexDefinition{
		Kind:     "ServiceIncident",
		Ancestor: true,
		SortBy: []datastore.IndexColumn{
			{
				Property:   "ID",
				Descending: true,
			},
		},
	}

	indexes = []*datastore.IndexDefinition{&serviceIdx, &incidentIdx}
)

type getServiceTest struct {
	inputID    string
	expService *Service
	expError   error
}

func newTestContext() context.Context {
	ctx := gaetesting.TestingContext()
	testing := datastore.GetTestable(ctx)
	testing.Consistent(true)
	testing.AddIndexes(indexes...)
	return ctx
}

func TestGetService(t *testing.T) {
	ctx := newTestContext()
	testService := &Service{
		ID:   "testservice",
		Name: "Test Service",
		SLA:  "www.google.com",
	}
	datastore.Put(ctx, testService)

	service, err := GetService(ctx, testService.ID)
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if !reflect.DeepEqual(testService, service) {
		t.Errorf("Expected service: %v. Found service: %v",
			testService, service)
	}

	service, err = GetService(ctx, "ghost")
	if err != nil {
		t.Errorf("Expect no errors. Found: %v", err)
	}
	if service != nil {
		t.Errorf("Expected nil service. Found: %v", service)
	}
}
