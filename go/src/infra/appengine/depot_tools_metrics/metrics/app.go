// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package metrics stores the reported JSON metrics from depot_tools into a
// BigQuery table.
package metrics

import (
	"fmt"
	"net/http"

	"cloud.google.com/go/bigquery"
	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/bq"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"google.golang.org/appengine"
	"infra/appengine/depot_tools_metrics/schema"
)

const (
	projectID string = "cit-cli-metrics"
	datasetID string = "metrics"
	tableID   string = "depot_tools"
)

func init() {
	r := router.New()
	standard.InstallHandlers(r)

	m := standard.Base().Extend(CheckTrustedIP)

	r.GET("/should-upload", m, shouldUploadHandler)
	r.POST("/upload", m, uploadHandler)

	http.DefaultServeMux.Handle("/", r)
}

// CheckTrustedIP continues if the request in coming from a corp machine,
// and thus a Googler; or exits with a 403 status code otherwise.
func CheckTrustedIP(c *router.Context, next router.Handler) {
	// TRUSTED_IP_REQUEST=1 means the request is coming from a corp machine.
	if c.Request.Header.Get("X-AppEngine-Trusted-IP-Request") != "1" {
		http.Error(c.Writer, "Access Denied: You're not on corp.", http.StatusForbidden)
		return
	}
	next(c)
}

// shouldUploadHandler handles the '/should-upload' endpoint, which is used by
// depot_tools to check whether it should collect and upload metrics.
func shouldUploadHandler(c *router.Context) {
	fmt.Fprintf(c.Writer, "Success")
}

// uploadHandler handles the '/upload' endpoint, which is used by depot_tools
// to upload the collected metrics in a JSON format. It enforces the schema
// defined in 'metrics_schema.json' and writes the data to the BigQuery table
// projectID.datasetID.tableID.
func uploadHandler(c *router.Context) {
	var metrics schema.Metrics
	err := jsonpb.Unmarshal(c.Request.Body, &metrics)
	if err != nil {
		logging.Errorf(c.Context, "Could not extract metrics: %v", err)
		http.Error(c.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	if err := checkConstraints(metrics); err != nil {
		logging.Errorf(c.Context, "The metrics don't obey constraints: %v", err)
		http.Error(c.Writer, err.Error(), http.StatusBadRequest)
		return
	}

	reportDepotToolsMetrics(c.Context, metrics)

	ctx := appengine.WithContext(c.Context, c.Request)
	err = putMetrics(ctx, metrics)
	if err != nil {
		logging.Errorf(c.Context, "Could not write to BQ: %v", err)
		http.Error(c.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	fmt.Fprintf(c.Writer, "Success")
}

// putMetrics extracts the Metrics from the request and streams them into the
// BigQuery table.
func putMetrics(ctx context.Context, metrics schema.Metrics) error {
	client, err := bigquery.NewClient(ctx, projectID)
	if err != nil {
		return err
	}

	up := bq.NewUploader(ctx, client, datasetID, tableID)
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true

	return up.Put(ctx, &metrics)
}
