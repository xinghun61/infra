// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io"

	"cloud.google.com/go/bigquery"
	"golang.org/x/net/context"
)

type dryRunTableStore struct {
	ts tableStore
	w  io.Writer
}

func (ts dryRunTableStore) getTableMetadata(ctx context.Context, datasetID, tableID string) (*bigquery.TableMetadata, error) {
	fmt.Fprintf(ts.w, "Running getTableMetadata for datasetID %v tableID %v\n", datasetID, tableID)
	md, err := ts.ts.getTableMetadata(ctx, datasetID, tableID)
	if err != nil {
		fmt.Fprintln(ts.w, err)
	}
	fmt.Fprintf(ts.w, "Got %v\n", md)
	return md, nil
}

func (ts dryRunTableStore) createTable(ctx context.Context, datasetID, tableID string, option ...bigquery.CreateTableOption) error {
	fmt.Fprintf(ts.w, "Would run createTable with datasetID %v, tableID %v, options %+v\n", datasetID, tableID, option)
	return nil
}

func (ts dryRunTableStore) updateTable(ctx context.Context, datasetID, tableID string, toUpdate bigquery.TableMetadataToUpdate) error {
	fmt.Fprintf(ts.w, "Would run updateTable with datasetID %v, tableID %v\n", datasetID, tableID)
	fmt.Fprintf(ts.w, "Using TableMetadataToUpdate{Name: %v, Description: %v}\n", toUpdate.Name, toUpdate.Description)
	fmt.Fprintln(ts.w, "And schema:")
	for _, p := range toUpdate.Schema {
		fmt.Fprintf(ts.w, "%+v\n", *p)
	}
	return nil
}
