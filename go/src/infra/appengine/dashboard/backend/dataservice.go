// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"fmt"
	"sync"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
)

// Severity represents the alert type.
type Severity int

const (
	// Ignore first value, 0. Start assignments at iota=1 to match dashpb.Severity.
	_ Severity = iota
	// SeverityRed represents paging alerts.
	SeverityRed
	// SeverityYellow represents email alerts.
	SeverityYellow
)

// IncidentStatus represents a status category of a ServiceIncident.
type IncidentStatus int

const (
	// IncidentStatusAny represents a status that is either Open or Closed.
	IncidentStatusAny IncidentStatus = iota
	// IncidentStatusOpen represents the status of Open ServiceIncidents.
	IncidentStatusOpen
	// IncidentStatusClosed represents the status of Closed ServiceIncidents.
	IncidentStatusClosed
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

// QueryOptions contains maps for additional query options that indicate interface{} value
// the fields should match.
type QueryOptions struct {
	After  time.Time      // if non-zero, a start of time range to fetch
	Before time.Time      // if non-zero, an end of time range to fetch
	Status IncidentStatus // indicates the status the fetched incidents should have
}

// BuildQuery builds a datastore Query from the values of this QueryOptions.
// If this QueryOptions has a non-zero After or a non-zero Before and a timeField
// is not provided, an error will be thrown.
//
// It returns (query, nil) on success or (nil, err) if the timeField is empty while
// either After or Before is non-zero.
func (q *QueryOptions) BuildQuery(query *datastore.Query, timeField string) (*datastore.Query, error) {
	switch q.Status {
	case IncidentStatusOpen:
		query = query.Eq("Open", true)
	case IncidentStatusClosed:
		query = query.Eq("Open", false)
	}
	if !q.After.IsZero() {
		query = query.Gte(timeField, q.After)
	}
	if !q.Before.IsZero() {
		query = query.Lte(timeField, q.Before)
	}
	_, err := query.Finalize()
	if err != nil {
		return nil, err
	}
	return query, nil
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
			c, "entity not found, using serviceID: %s and incident id: %s",
			serviceID, id)
		return nil, nil
	default:
		logging.Errorf(c, "error getting Service entity: %s", err)
		return nil, err
	}
}

// GetServiceIncidents gets all the incidents of the given service.
// If onlyOpen is true, this will only return open Incidents. If it is false
// it will return all Incidents, open and closed.
//
// It returns (incidents, nil) on success or (nil, err) on datastore errors.
// If no incidents for the service were found, incidents will be empty.
func GetServiceIncidents(c context.Context, serviceID string, queryOpts *QueryOptions) ([]ServiceIncident, error) {
	serviceKey := datastore.NewKey(c, "Service", serviceID, 0, nil)
	baseQuery := datastore.NewQuery("ServiceIncident").Ancestor(serviceKey)
	var queries []*datastore.Query
	switch {
	case queryOpts == nil:
		queries = []*datastore.Query{baseQuery}
	case !queryOpts.After.IsZero() || !queryOpts.Before.IsZero():
		byStartTime, err := queryOpts.BuildQuery(baseQuery, "StartTime")
		if err != nil {
			logging.Errorf(c, "error building query from queryOpts: %s", err)
			return nil, err
		}
		byEndTime, err := queryOpts.BuildQuery(baseQuery, "EndTime")
		if err != nil {
			logging.Errorf(c, "error building query from queryOpts: %s", err)
			return nil, err
		}
		queries = []*datastore.Query{byStartTime, byEndTime}
	default:
		query, err := queryOpts.BuildQuery(baseQuery, "")
		if err != nil {
			logging.Errorf(c, "error building query from queryOpts: %s", err)
			return nil, err
		}
		queries = []*datastore.Query{query}
	}
	return consolidateQueryResults(c, queries)
}

func consolidateQueryResults(c context.Context, queries []*datastore.Query) ([]ServiceIncident, error) {
	type incidentsOrError struct {
		incidents []ServiceIncident
		err       error
	}
	results := make([]incidentsOrError, len(queries))
	wg := sync.WaitGroup{}
	for i, query := range queries {
		wg.Add(1)
		go func(i int, query *datastore.Query) {
			defer wg.Done()
			incidents := []ServiceIncident{}
			err := datastore.GetAll(c, query, &incidents)
			results[i] = incidentsOrError{incidents, err}
		}(i, query)
	}
	wg.Wait()

	resultsByID := map[string]bool{}
	incidents := []ServiceIncident{}
	for i, result := range results {
		if result.err != nil {
			logging.Errorf(c, "error getting ServiceIncident entities: %s for query: %v", result.err, queries[i])
			return nil, result.err
		}
		for _, incident := range result.incidents {
			if _, exists := resultsByID[incident.ID]; !exists {
				incidents = append(incidents, incident)
				resultsByID[incident.ID] = true
			}
		}
	}
	return incidents, nil
}

// GetService gets the specified Service from datastore.
//
// It returns (service, nil) on success, (nil, nil) if such service is not found
// or (nil, err) on datastore errors.
func GetService(c context.Context, serviceID string) (*Service, error) {
	service := Service{ID: serviceID}
	switch err := datastore.Get(c, &service); {
	case err == nil:
		return &service, nil
	case err == datastore.ErrNoSuchEntity:
		logging.Errorf(c, "entity not found: %s", err)
		return nil, nil
	default:
		logging.Errorf(c, "error getting Service entity: %s", err)
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
		logging.Errorf(c, "error getting Service entities: %s", err)
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
		logging.Errorf(c, "encountered datastore error: %s", err)
		return err
	}
	if !existsResults.All() {
		return fmt.Errorf("a Service with ID: %q does not exist in datastore", serviceID)
	}
	return datastore.RunInTransaction(c, func(c context.Context) error {
		incidentKey := datastore.NewKey(c, "ServiceIncident", id, 0, serviceKey)
		existsResults, err = datastore.Exists(c, incidentKey)
		if err != nil {
			logging.Errorf(c, "encountered datastore error: %s", err)
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
			logging.Errorf(c, "error writing incident to datastore: %s", err)
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
func CloseIncident(c context.Context, id, serviceID string) error {
	return datastore.RunInTransaction(c, func(c context.Context) error {
		incident, err := GetIncident(c, id, serviceID)
		if incident == nil {
			if err == nil {
				return fmt.Errorf(
					"incident with ServiceID: %s and incident id: %s not found in datastore",
					serviceID, id)
			}
			return err
		}
		incident.EndTime = time.Now().UTC()
		incident.Open = false
		if err := datastore.Put(c, incident); err != nil {
			logging.Errorf(c, "error writing updated incident to datastore: %s", err)
			return err
		}
		return nil
	}, nil)
}
