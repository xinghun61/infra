// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"fmt"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/logging"
)

// Severity represents the alert type.
type Severity int

const (
	// SeverityRed represents paging alerts.
	SeverityRed Severity = 0
	// SeverityYellow represents email alerts.
	SeverityYellow Severity = 1
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

// GetServiceIncidents gets all the incidents of the given service.
// If onlyOpen is true, this will only return open Incidents. If it is false
// it will return all Incidents, open and closed.
//
// It returns (incidents, nil) on success or (nil, err) on datastore errors.
// If no incidents for the service were found, incidents will be empty.
func GetServiceIncidents(c context.Context, serviceID string, onlyOpen bool) ([]ServiceIncident, error) {
	serviceKey := datastore.NewKey(c, "Service", serviceID, 0, nil)
	query := datastore.NewQuery("ServiceIncident").Ancestor(serviceKey)
	if onlyOpen {
		query = query.Eq("Open", true)
	}
	incidents := []ServiceIncident{}
	if err := datastore.GetAll(c, query, &incidents); err != nil {
		logging.Errorf(c, "Error getting ServiceIncident entities: %v", err)
		return nil, err
	}
	return incidents, nil
}

// GetService gets the specified Service from datastore.
//
// It returns (service, nil) on success, (nil, nil) if such service is not found
// or (nil, err) on datstore errors.
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

// GetAllServices gets all Service entities from datastore.
//
// It returns (services, nil) on success or () (nil, err) on datastore errors.
func GetAllServices(c context.Context) ([]Service, error) {
	query := datastore.NewQuery("Service")
	services := []Service{}
	if err := datastore.GetAll(c, query, &services); err != nil {
		logging.Errorf(c, "Error getting Service entities: %v", err)
		return nil, err
	}
	return services, nil
}

// AddIncident writes an incident to datastore.
//
// On success, nil is returned. If no Service with the given serviceID is found or if
// a ServiceIncident with the same ID is found, err is returned. If there is a datastore error
// err is returned.
func AddIncident(c context.Context, id string, serviceID string, severity Severity) error {
	serviceKey := datastore.NewKey(c, "Service", serviceID, 0, nil)
	existsResults, err := datastore.Exists(c, serviceKey)
	if err != nil {
		logging.Errorf(c, "encountered datastore error: %v", err)
		return err
	}
	if !existsResults.All() {
		return fmt.Errorf("a Service with ID: %q does not exist in datastore", serviceID)
	}
	return datastore.RunInTransaction(c, func(c context.Context) error {
		incidentKey := datastore.NewKey(c, "ServiceIncident", id, 0, serviceKey)
		existsResults, err = datastore.Exists(c, incidentKey)
		if err != nil {
			logging.Errorf(c, "encountered datastore error: %v", err)
			return err
		}
		if existsResults.All() {
			return fmt.Errorf("an Incident with ID: %q already exists", id)
		}
		incident := ServiceIncident{
			ID:         id,
			ServiceKey: serviceKey,
			Open:       true,
			StartTime:  time.Now().UTC(),
			Severity:   severity,
		}
		if err := datastore.Put(c, &incident); err != nil {
			logging.Errorf(c, "error writing incident to datastore: %v", err)
			return err
		}
		return nil
	}, nil)
}

// CloseIncident updates an existing ServiceIncident by setting a value for the EndTime to the
// current time.
//
// It returns nil on success. If there is an error getting the Incident or updating the Incident,
// or the Incident was never found, err will be returned.
func CloseIncident(c context.Context, id string, serviceID string) error {
	return datastore.RunInTransaction(c, func(c context.Context) error {
		incident, err := GetIncident(c, id, serviceID)
		if incident == nil {
			if err == nil {
				return fmt.Errorf(
					"incident with ServiceID: %v and incident id: %v not found in datastore",
					serviceID, id)
			}
			return err
		}
		incident.EndTime = time.Now().UTC()
		incident.Open = false
		if err := datastore.Put(c, incident); err != nil {
			logging.Errorf(c, "error writing updated incident to datastore: %v", err)
			return err
		}
		return nil
	}, nil)
}
