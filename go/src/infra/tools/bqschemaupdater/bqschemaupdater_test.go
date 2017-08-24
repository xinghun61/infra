// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"reflect"
	"testing"

	pb "infra/libs/bqschema/tabledef"

	"cloud.google.com/go/bigquery"
	"golang.org/x/net/context"
)

func TestBQSchema(t *testing.T) {
	f := []*pb.FieldSchema{
		{
			Name:        "test_field",
			Description: "test description",
			Type:        pb.Type_STRING,
			IsRepeated:  true,
		},
	}
	got := bqSchema(f)
	want := bigquery.Schema{
		&bigquery.FieldSchema{
			Name:        "test_field",
			Description: "test description",
			Type:        bigquery.StringFieldType,
			Repeated:    true,
		},
	}
	if !(reflect.DeepEqual(got, want)) {
		t.Errorf("got: %v; want: %v", got, want)
	}
}

func TestBQField(t *testing.T) {
	f := &pb.FieldSchema{
		Name:        "test_field",
		Description: "test description",
		Type:        pb.Type_RECORD,
		IsRepeated:  true,
		Schema: []*pb.FieldSchema{
			{
				Name:        "nested_field",
				Description: "i am nested",
				Type:        pb.Type_STRING,
				IsRequired:  true,
			},
		},
	}
	got := bqField(f)
	want := &bigquery.FieldSchema{
		Name:        "test_field",
		Description: "test description",
		Type:        bigquery.RecordFieldType,
		Repeated:    true,
		Schema: []*bigquery.FieldSchema{
			{
				Name:        "nested_field",
				Description: "i am nested",
				Type:        "STRING",
				Required:    true,
			},
		},
	}
	if !(reflect.DeepEqual(got, want)) {
		t.Errorf("got: %v; want: %v", got, want)
	}
}

func TestUpdateFromTableDef(t *testing.T) {
	ctx := context.Background()
	ts := localTableStore{}
	datasetID := pb.TableDef_AGGREGATED.ID()
	tableID := "test_table"

	field := &pb.FieldSchema{
		Name:        "test_field",
		Description: "test description",
		Type:        pb.Type_STRING,
	}
	anotherField := &pb.FieldSchema{
		Name:        "field_2",
		Description: "another field",
		Type:        pb.Type_STRING,
	}
	tcs := [][]*pb.FieldSchema{
		{field},
		{field, anotherField},
	}
	for _, tc := range tcs {
		td := &pb.TableDef{
			Dataset: pb.TableDef_AGGREGATED,
			TableId: tableID,
			Fields:  tc,
		}
		err := updateFromTableDef(ctx, ts, td)
		if err != nil {
			t.Fatal(err)
		}
		got, err := ts.getTableMetadata(ctx, datasetID, tableID)
		if err != nil {
			t.Fatal(err)
		}
		want := &bigquery.TableMetadata{Schema: bqSchema(tc)}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("got: %v; want: %v", got, want)
		}
	}
}
