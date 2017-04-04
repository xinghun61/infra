// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"
)

// Severity represents the alert type.
type Severity int

const (
	// SeverityRed represents paging alerts.
	SeverityRed Severity = 1
	// SeverityYellow represents email alerts.
	SeverityYellow Severity = 2
)

var (
	serviceIDs = []string{"monorail", "som"}
)

// ServiceIncident contains incident details and its parent service key.
type ServiceIncident struct {
	ID         string         `gae:"$id"`
	ServiceKey *datastore.Key `gae:"$parent"`
	Open       bool
	StartTime  time.Time
	EndTime    time.Time
	Severity   Severity
}

// Service contains basic service information and has ServiceIncidents as child entities.
type Service struct {
	ID   string `gae:"$id"` // eg. "monorail", "som"
	Name string // eg. "Monorail", "Sheriff-O-Matic"
	SLA  string
}

// GetIncident gets the specified ServiceIncident from datastore.
//
// It returns (incident, nil) on success, (nil, nil) if such incident is not found
// or (nil, err) on datastore errors
func GetIncident(c context.Context, id string, serviceID string) (*ServiceIncident, error) {
	incident := ServiceIncident{
		ID:         id,
		ServiceKey: datastore.NewKey(c, "Service", serviceID, 0, nil),
	}
	switch err := datastore.Get(c, &incident); {
	case err == nil:
		return &incident, nil
	case err == datastore.ErrNoSuchEntity:
		logging.Errorf(
			c, "Entity not found. Using serviceID: %v and incident id: %v",
			serviceID, id)
		return nil, nil
	default:
		logging.Errorf(c, "Error getting Service entity: %v", err)
		return nil, err
	}
}

// GetService gets the specified Service from datastore.
//
// It returns (service, nil) on success, (nil, nil) if such service is not found
// or (nil, err) on datstore errors
func GetService(c context.Context, serviceID string) (*Service, error) {
	service := Service{ID: serviceID}
	switch err := datastore.Get(c, &service); {
	case err == nil:
		return &service, nil
	case err == datastore.ErrNoSuchEntity:
		logging.Errorf(c, "Entity not found: %v", err)
		return nil, nil
	default:
		logging.Errorf(c, "Error getting Service entity: %v", err)
		return nil, err
	}
}
