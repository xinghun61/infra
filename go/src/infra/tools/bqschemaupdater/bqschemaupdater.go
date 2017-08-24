// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main takes as an argument the file path of a schema to be added to
// or updated in BigQuery. That file should contain a tabledef.TableDef proto
// in text format.
package main

import (
	"flag"
	"log"
	"os"
	"time"

	pb "infra/libs/bqschema/tabledef"
	"infra/libs/infraenv"

	"go.chromium.org/luci/common/auth"

	"cloud.google.com/go/bigquery"
	"github.com/golang/protobuf/jsonpb"
	"google.golang.org/api/option"

	"golang.org/x/net/context"
)

func loadTableDef(path string) (*pb.TableDef, error) {
	r, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer r.Close()

	td := &pb.TableDef{}
	if err := jsonpb.Unmarshal(r, td); err != nil {
		return nil, err
	}
	return td, nil
}

func updateFromTableDef(ctx context.Context, ts tableStore, td *pb.TableDef) error {
	_, err := ts.getTableMetadata(ctx, td.Dataset.ID(), td.TableId)
	if errNotFound(err) {
		var options []bigquery.CreateTableOption
		if td.PartitionTable {
			i := int(td.PartitionExpirationSeconds)
			tp := bigquery.TimePartitioning{Expiration: time.Duration(i) * time.Second}
			options = append(options, tp)
		}
		err = ts.createTable(ctx, td.Dataset.ID(), td.TableId, options...)
		if err != nil {
			return err
		}
	}
	md := bigquery.TableMetadataToUpdate{
		Name:        td.Name,
		Description: td.Description,
		Schema:      pb.BQSchema(td.Fields),
	}
	err = ts.updateTable(ctx, td.Dataset.ID(), td.TableId, md)
	return err
}

func main() {
	ctx := context.Background()

	dry := flag.Bool("dry-run", false, "Only performs non-mutating operations; logs what would happen otherwise")
	project := flag.String("project", infraenv.ChromeInfraEventsProject, "Cloud project that the table belongs to.")

	flag.Parse()
	file := flag.Arg(0)
	if file == "" {
		log.Fatal("Missing arg: file path for schema to add/update")
	}
	td, err := loadTableDef(file)
	if err != nil {
		log.Fatalf("Failed to load TableDef from %q: %s", file, err)
	}

	// Create an Authenticator and use it for BigQuery operations.
	authOpts := infraenv.DefaultAuthOptions()
	authOpts.Scopes = []string{bigquery.Scope}
	authenticator := auth.NewAuthenticator(ctx, auth.InteractiveLogin, authOpts)

	authTS, err := authenticator.TokenSource()
	if err != nil {
		log.Fatalf("Could not get authentication credentials: %s", err)
	}

	c, err := bigquery.NewClient(ctx, *project, option.WithTokenSource(authTS))
	if err != nil {
		log.Fatalf("Could not create BigQuery client: %s", err)
	}
	var ts tableStore
	ts = bqTableStore{c}
	if *dry {
		ts = dryRunTableStore{ts: ts, w: os.Stdout}
	}

	log.Printf("Updating dataset %q, table %q in project %q...", td.Dataset.ID(), td.TableId, *project)
	err = updateFromTableDef(ctx, ts, td)
	if err != nil {
		log.Fatalf("Failed to update table: %s", err)
	}

	log.Println("Finished updating table.")
}
