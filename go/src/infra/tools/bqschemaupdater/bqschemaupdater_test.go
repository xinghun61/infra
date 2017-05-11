// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"

	"cloud.google.com/go/bigquery"
	"golang.org/x/net/context"
)

func TestBQSchema(t *testing.T) {
	f := []FieldSchema{
		{
			Name:        "test_field",
			Description: "test description",
			Type:        "STRING",
			Repeated:    true,
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
	f := FieldSchema{
		Name:        "test_field",
		Description: "test description",
		Type:        "RECORD",
		Repeated:    true,
		Schema: []FieldSchema{
			{
				Name:        "nested_field",
				Description: "i am nested",
				Type:        "STRING",
				Required:    true,
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

func TestTableDefs(t *testing.T) {
	s := []TableDef{
		{
			DatasetID: "test_dataset",
			TableID:   "test_table",
			Fields: []FieldSchema{
				{
					Name:        "field1",
					Type:        "RECORD",
					Description: "test field",
					Schema: []FieldSchema{
						{
							Name:        "nested",
							Type:        "STRING",
							Description: "nested",
						},
					},
				},
				{
					Name:        "field2",
					Type:        "INTEGER",
					Description: "test field 2",
				},
			},
		},
	}
	j, err := json.Marshal(&s)
	if err != nil {
		t.Fatal(err)
	}
	got := tableDefs(strings.NewReader(string(j)))
	want := s
	if !(reflect.DeepEqual(got, want)) {
		t.Errorf("got: %v; want: %v", got, want)
	}
}

func TestUpdateFromTableDef(t *testing.T) {
	ctx := context.Background()
	ts := localTableStore{}
	datasetID := "test_dataset"
	tableID := "test_table"

	field := FieldSchema{
		Name:        "test_field",
		Description: "test description",
		Type:        "STRING",
	}
	anotherField := FieldSchema{
		Name:        "field_2",
		Description: "another field",
		Type:        "STRING",
	}
	tcs := [][]FieldSchema{
		{field},
		{field, anotherField},
	}
	for _, tc := range tcs {
		td := TableDef{
			DatasetID: datasetID,
			TableID:   tableID,
			Fields:    tc,
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
