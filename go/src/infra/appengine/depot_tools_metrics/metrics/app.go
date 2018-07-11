// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package metrics stores the reported JSON metrics from depot_tools into a
// BigQuery table.
package metrics

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"math/rand"
	"net/http"

	"cloud.google.com/go/bigquery"
	"github.com/xeipuuv/gojsonschema"
	"golang.org/x/net/context"
	"google.golang.org/appengine"
)

const (
	projectID string = "cit-cli-metrics"
	datasetID string = "metrics"
	tableID   string = "depot_tools"
)

// The Metrics reported by depot_tools. A map from string to bigquery.Value
// (i.e. interface{}), where the metrics extracted from the reported JSON will
// be stored.
type Metrics map[string]bigquery.Value

// Save implements the bigquery.ValueSaver interface for Metrics, which is
// needed to be able to stream the data into a BigQuery table.
func (m Metrics) Save() (map[string]bigquery.Value, string, error) {
	insertID := fmt.Sprintf("%d", rand.Int())
	return m, insertID, nil
}

func init() {
	http.HandleFunc("/should-upload", shouldUploadHandler)
	http.HandleFunc("/upload", uploadHandler)
}

// shouldUploadHandler handles the '/should-upload' endpoint, which is used by
// depot_tools to check whether it should collect and upload metrics.
// It returns 200 if the request in coming from a corp machine, and thus a
// Googler, and 403 otherwise.
func shouldUploadHandler(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/should-upload" {
		http.NotFound(w, r)
		return
	}
	// TRUSTED_IP_REQUEST=1 means the request is coming from a corp machine.
	if r.Header.Get("X-AppEngine-Trusted-IP-Request") != "1" {
		http.Error(w, "Access Denied: You're not on corp.", http.StatusForbidden)
		return
	}
	fmt.Fprintf(w, "Success")
}

// uploadHandler handles the '/upload' endpoint, which is used by depot_tools
// to upload the collected metrics in a JSON format. It enforces the schema
// defined in 'metrics_schema.json' and writes the data to the BigQuery table
// projectID.datasetID.tableID.
// It returns 200 if the request suceeds, 300 if there was an internal error
// and 403 if the connection is not coming from a corp machine.
func uploadHandler(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/upload" {
		http.NotFound(w, r)
		return
	}
	// TRUSTED_IP_REQUEST=1 means the request is comming from a corp machine.
	if r.Header.Get("X-AppEngine-Trusted-IP-Request") != "1" {
		http.Error(w, "Access Denied: You're not on corp.", http.StatusForbidden)
		return
	}

	// Create a new App Engine context from the request.
	ctx := appengine.NewContext(r)

	err := putMetrics(ctx, r.Body)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	fmt.Fprintf(w, "Success")
}

// extractMetrics extracts the Metrics from the request, and enforces the JSON
// schema defined in 'metrics_schema.json'.
func extractMetrics(content io.Reader) (Metrics, error) {
	var metrics Metrics
	err := json.NewDecoder(content).Decode(&metrics)
	if err != nil {
		return metrics, err
	}
	schema, err := ioutil.ReadFile("metrics_schema.json")
	if err != nil {
		return metrics, err
	}
	schemaLoader := gojsonschema.NewStringLoader(string(schema[:]))
	documentLoader := gojsonschema.NewGoLoader(metrics)
	result, err := gojsonschema.Validate(schemaLoader, documentLoader)
	if err != nil {
		return metrics, err
	}
	if !result.Valid() {
		errs := ""
		for _, err := range result.Errors() {
			errs += err.Description() + "\n"
		}
		return metrics, errors.New(errs)
	}
	return metrics, nil
}

// putMetrics extracts the Metrics from the request and streams them into the
// BigQuery table.
func putMetrics(ctx context.Context, request io.Reader) error {
	client, err := bigquery.NewClient(ctx, projectID)
	if err != nil {
		return err
	}

	metrics, err := extractMetrics(request)
	if err != nil {
		return err
	}

	up := client.Dataset(datasetID).Table(tableID).Uploader()
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true

	return up.Put(ctx, metrics)
}
