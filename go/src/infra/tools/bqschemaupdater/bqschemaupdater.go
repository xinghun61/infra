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

// JSONTableDef is used for loading the necessary information for constructing a
// bigquery.Schema from JSON schema files
type JSONTableDef struct {
	DatasetID string        `json:"datasetID"`
	TableID   string        `json:"tableID"`
	Fields    []FieldSchema `json:"schema"`
}

// FieldSchema exactly mirrors bigquery.FieldSchema, and exists to provide json
// tags that are not present in bigquery.FieldSchema
type FieldSchema struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Description string `json:"description"`
}

type tableDef struct {
	datasetID string
	tableID   string
	toUpdate  bigquery.TableMetadataToUpdate
}

func tableDefs(j []JSONTableDef) []tableDef {
	var defs []tableDef
	for _, s := range j {
		def := tableDef{
			datasetID: s.DatasetID,
			tableID:   s.TableID,
			toUpdate: bigquery.TableMetadataToUpdate{
				Schema: bqSchema(s.Fields),
			},
		}
		defs = append(defs, def)
	}
	return defs
}

func bqSchema(fields []FieldSchema) bigquery.Schema {
	var s []*bigquery.FieldSchema
	for _, f := range fields {
		s = append(s, bqField(f))
	}
	return bigquery.Schema(s)
}

func bqField(f FieldSchema) *bigquery.FieldSchema {
	return &bigquery.FieldSchema{
		Name:        f.Name,
		Description: f.Description,
		Type:        bigquery.FieldType(f.Type),
	}
}

func jsonTableDefs(r io.Reader) []JSONTableDef {
	var s []JSONTableDef
	d := json.NewDecoder(r)
	err := d.Decode(&s)
	if err != nil {
		log.Fatal(err)
	}
	return s
}

func updateFromTableDef(ctx context.Context, ts tableStore, td tableDef) error {
	_, err := ts.getTableMetadata(ctx, td.datasetID, td.tableID)
	if errNotFound(err) {
		err = ts.createTable(ctx, td.datasetID, td.tableID)
		if err != nil {
			return err
		}
	}
	err = ts.updateTable(ctx, td.datasetID, td.tableID, td.toUpdate)
	return err
}

// TODO: Handle repeated fields, record fields
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
	tds := tableDefs(jsonTableDefs(r))

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
