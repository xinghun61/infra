// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package monitoring provides common monitoring code for Lucifer.

Monitoring configuration is global to the program.  This package sets
up Stackdriver Trace, BigQuery, and tsmon.

A top level trace is set up with the program name, taken from the
first command argument.
*/
package monitoring

import (
	"context"
	"errors"
	"log"
	"os"
	"path/filepath"

	"cloud.google.com/go/bigquery"
	"contrib.go.opencensus.io/exporter/stackdriver"
	"go.chromium.org/luci/common/tsmon"
	"go.chromium.org/luci/common/tsmon/target"
	"go.opencensus.io/trace"
)

var programName = filepath.Base(os.Args[0])

var bigQueryClient *bigquery.Client

// Config describes configuration for Setup.
type Config struct {
	GCPProject string
	TsmonFlags *tsmon.Flags
}

// Closer is used to group all of the cleanup actions needed for
// monitoring.
type Closer struct {
	exporter       *stackdriver.Exporter
	tsmonCtx       *context.Context
	bigQueryClient *bigquery.Client
	span           *trace.Span
}

// Close closes the Closer.
func (c *Closer) Close() error {
	// Cleanup should be performed in reverse order of Setup.
	if c.span != nil {
		c.span.End()
	}
	if c.bigQueryClient != nil {
		if err := c.bigQueryClient.Close(); err != nil {
			log.Printf("Error closing BigQuery client: %s", err)
		}
	}
	if c.tsmonCtx != nil {
		tsmon.Shutdown(*c.tsmonCtx)
	}
	if c.exporter != nil {
		c.exporter.Flush()
	}
	return nil
}

// Setup configures monitoring based on the given Config.  Make sure
// to defer a call to Closer.Close.  Errors in setting up monitoring
// components will be logged and ignored so the caller does not need
// to worry about stopping the entire program (better to have no
// metrics and think there is an outage than to actually have an
// outage).
func Setup(ctx context.Context, c Config) (context.Context, *Closer) {
	cl := &Closer{}
	if e, err := setupTrace(c.GCPProject); err != nil {
		log.Printf("Error setting up Stackdriver Trace: %s", err)
	} else {
		cl.exporter = e
	}
	if err := setupTsmon(ctx, c.TsmonFlags); err != nil {
		log.Printf("Error setting up tsmon: %s", err)
	} else {
		cl.tsmonCtx = &ctx
	}
	b, err := bigquery.NewClient(ctx, c.GCPProject)
	if err != nil {
		log.Printf("Error setting up BigQuery client: %s", err)
	} else {
		cl.bigQueryClient = b
		bigQueryClient = b
	}
	ctx, cl.span = trace.StartSpan(ctx, programName, trace.WithSampler(trace.AlwaysSample()))
	return ctx, cl
}

func setupTrace(project string) (*stackdriver.Exporter, error) {
	o := stackdriver.Options{
		ProjectID: project,
	}
	e, err := stackdriver.NewExporter(o)
	if err != nil {
		return nil, err
	}
	trace.RegisterExporter(e)
	return e, nil
}

func setupTsmon(ctx context.Context, fl *tsmon.Flags) error {
	configureTsmonFlags(fl)
	if err := tsmon.InitializeFromFlags(ctx, fl); err != nil {
		return err
	}
	return nil
}

func configureTsmonFlags(fl *tsmon.Flags) {
	fl.Flush = tsmon.FlushManual
	fl.Target.SetDefaultsFromHostname()
	fl.Target.TargetType = target.TaskType
	fl.Target.TaskServiceName = programName
	fl.Target.TaskJobName = programName
}

// BQClient returns the bigquery.Client that is created by Setup.
// This function returns an error if BigQuery is not set up yet.
func BQClient() (*bigquery.Client, error) {
	if bigQueryClient == nil {
		return nil, errors.New("BigQuery client not set up")
	}
	return bigQueryClient, nil
}
