// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main takes as an argument the file path of a schema to be added to
// or updated in BigQuery. That file should contain a tabledef.TableDef proto
// in text format.
package main

import (
	"flag"
	"io"
	"log"
	"os"
	"strconv"
	"time"

	"cloud.google.com/go/bigquery"
	"github.com/golang/protobuf/jsonpb"
	"golang.org/x/net/context"
	pb "infra/libs/bqschema/tabledef"
)

func bqSchema(fields []*pb.FieldSchema) bigquery.Schema {
	var s bigquery.Schema
	for _, f := range fields {
		s = append(s, bqField(f))
	}
	return s
}

func bqField(f *pb.FieldSchema) *bigquery.FieldSchema {
	fs := &bigquery.FieldSchema{
		Name:        f.Name,
		Description: f.Description,
		Type:        bigquery.FieldType(f.Type.String()),
		Repeated:    f.IsRepeated,
		Required:    f.IsRequired,
	}
	if fs.Type == bigquery.RecordFieldType {
		fs.Schema = bqSchema(f.Schema)
	}
	return fs
}

func tableDef(r io.Reader) *pb.TableDef {
	td := &pb.TableDef{}
	err := jsonpb.Unmarshal(r, td)
	if err != nil {
		log.Fatal(err)
	}
	return td
}

func updateFromTableDef(ctx context.Context, ts tableStore, td *pb.TableDef) error {
	_, err := ts.getTableMetadata(ctx, td.DatasetId, td.TableId)
	if errNotFound(err) {
		var options []bigquery.CreateTableOption
		if td.PartitionTable {
			i := int(td.PartitionExpirationSeconds)
			d, err := time.ParseDuration(strconv.Itoa(i) + "s")
			if err != nil {
				return err
			}
			tp := bigquery.TimePartitioning{Expiration: d}
			options = append(options, tp)
		}
		err = ts.createTable(ctx, td.DatasetId, td.TableId, options...)
		if err != nil {
			return err
		}
	}
	md := bigquery.TableMetadataToUpdate{
		Name:        td.Name,
		Description: td.Description,
		Schema:      bqSchema(td.Fields),
	}
	err = ts.updateTable(ctx, td.DatasetId, td.TableId, md)
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
	td := tableDef(r)

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

	err = updateFromTableDef(ctx, ts, td)
	if err != nil {
		log.Fatal(err)
	}
}
