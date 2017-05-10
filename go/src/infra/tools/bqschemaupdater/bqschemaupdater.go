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

// JSONSchema is used for loading the necessary information for constructing a
// bigquery.Schema from JSON schema files
type JSONSchema struct {
	DatasetID string      `json:"datasetID"`
	TableID   string      `json:"tableID"`
	Fields    []JSONField `json:"fields"`
}

// JSONField is used for loading the necessary information for constructing a
// bigquery.FieldSchema from JSON schema files
type JSONField struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Description string `json:"description"`
}

type tableDef struct {
	datasetID string
	tableID   string
	toUpdate  bigquery.TableMetadataToUpdate
}

func tableDefs(schemas []JSONSchema) []tableDef {
	var defs []tableDef
	for _, s := range schemas {
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

func bqSchema(fields []JSONField) bigquery.Schema {
	var s []*bigquery.FieldSchema
	for _, f := range fields {
		s = append(s, bqField(f))
	}
	return bigquery.Schema(s)
}

func bqField(f JSONField) *bigquery.FieldSchema {
	return &bigquery.FieldSchema{
		Name:        f.Name,
		Description: f.Description,
		Type:        bigquery.FieldType(f.Type),
	}
}

func jsonSchemas(r io.Reader) []JSONSchema {
	var s []JSONSchema
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
	tds := tableDefs(jsonSchemas(r))

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
