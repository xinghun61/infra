// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"flag"
	"io"
	"log"
	"os"

	"cloud.google.com/go/bigquery"
	"golang.org/x/net/context"
)

// TableDef contains all the necessary information needed to create a BigQuery
// table. It is designed to be populated from a JSON config.
type TableDef struct {
	DatasetID   string        `json:"datasetID"`
	TableID     string        `json:"tableID"`
	Name        string        `json:"name"`
	Description string        `json:"description"`
	Fields      []FieldSchema `json:"schema"`
}

// FieldSchema exactly mirrors bigquery.FieldSchema, and exists to provide json
// tags that are not present in bigquery.FieldSchema.
type FieldSchema struct {
	Name        string        `json:"name"`
	Description string        `json:"description"`
	Repeated    bool          `json:"repeated"`
	Required    bool          `json:"required"`
	Type        string        `json:"type"`
	Schema      []FieldSchema `json:"schema"`
}

func bqSchema(fields []FieldSchema) bigquery.Schema {
	var s bigquery.Schema
	for _, f := range fields {
		s = append(s, bqField(f))
	}
	return s
}

func bqField(f FieldSchema) *bigquery.FieldSchema {
	fs := &bigquery.FieldSchema{
		Name:        f.Name,
		Description: f.Description,
		Type:        bigquery.FieldType(f.Type),
		Repeated:    f.Repeated,
		Required:    f.Required,
	}
	if fs.Type == bigquery.RecordFieldType {
		fs.Schema = bqSchema(f.Schema)
	}
	return fs
}

func tableDefs(r io.Reader) []TableDef {
	var s []TableDef
	d := json.NewDecoder(r)
	err := d.Decode(&s)
	if err != nil {
		log.Fatal(err)
	}
	return s
}

func updateFromTableDef(ctx context.Context, ts tableStore, td TableDef) error {
	_, err := ts.getTableMetadata(ctx, td.DatasetID, td.TableID)
	if errNotFound(err) {
		err = ts.createTable(ctx, td.DatasetID, td.TableID)
		if err != nil {
			return err
		}
	}
	md := bigquery.TableMetadataToUpdate{
		Name:        td.Name,
		Description: td.Description,
		Schema:      bqSchema(td.Fields),
	}
	err = ts.updateTable(ctx, td.DatasetID, td.TableID, md)
	return err
}

func main() {
	dry := flag.Bool("dry-run", false, "Only performs non-mutating operations; logs what would happen otherwise")
	flag.Parse()
	file := flag.Arg(0)
	if file == "" {
		log.Fatal("Missing arg: file path for schema to add/update")
	}
	r, err := os.Open(file)
	if err != nil {
		log.Fatal(err)
	}
	tds := tableDefs(r)

	ctx := context.Background()
	c, err := bigquery.NewClient(ctx, "chrome-infra-events")
	if err != nil {
		log.Fatal(err)
	}
	var ts tableStore
	ts = bqTableStore{c}
	if *dry {
		ts = dryRunTableStore{ts: ts, w: os.Stdout}
	}

	for _, td := range tds {
		err = updateFromTableDef(ctx, ts, td)
		if err != nil {
			log.Fatal(err)
		}
	}
}
