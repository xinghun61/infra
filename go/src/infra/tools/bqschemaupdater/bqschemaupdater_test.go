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

func TestTableDefs(t *testing.T) {
	s := []JSONTableDef{
		{
			DatasetID: "test_dataset",
			TableID:   "test_table",
			Fields: []FieldSchema{
				{
					Name:        "test_field",
					Description: "test description",
					Type:        "STRING",
				},
			},
		},
	}
	got := tableDefs(s)
	want := []tableDef{
		{
			datasetID: "test_dataset",
			tableID:   "test_table",
			toUpdate: bigquery.TableMetadataToUpdate{
				Schema: bigquery.Schema{
					&bigquery.FieldSchema{
						Name:        "test_field",
						Description: "test description",
						Type:        bigquery.StringFieldType,
					},
				},
			},
		},
	}
	if !(reflect.DeepEqual(got, want)) {
		t.Errorf("got: %v; want: %v", got, want)
	}
}

func TestBQSchema(t *testing.T) {
	f := []FieldSchema{
		{
			Name:        "test_field",
			Description: "test description",
			Type:        "STRING",
		},
	}
	got := bqSchema(f)
	want := bigquery.Schema{
		&bigquery.FieldSchema{
			Name:        "test_field",
			Description: "test description",
			Type:        bigquery.StringFieldType,
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
		Type:        "STRING",
	}
	got := bqField(f)
	want := &bigquery.FieldSchema{
		Name:        "test_field",
		Description: "test description",
		Type:        bigquery.StringFieldType,
	}
	if !(reflect.DeepEqual(got, want)) {
		t.Errorf("got: %v; want: %v", got, want)
	}
}

func TestJSONTableDefs(t *testing.T) {
	s := []JSONTableDef{
		{
			DatasetID: "test_dataset",
			TableID:   "test_table",
			Fields: []FieldSchema{
				{
					Name:        "field1",
					Type:        "STRING",
					Description: "test field",
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
	got := jsonTableDefs(strings.NewReader(string(j)))
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

	field := &bigquery.FieldSchema{
		Name:        "test_field",
		Description: "test description",
		Type:        bigquery.StringFieldType,
	}
	anotherField := &bigquery.FieldSchema{
		Name:        "field_2",
		Description: "another field",
		Type:        bigquery.StringFieldType,
	}
	tcs := [][]*bigquery.FieldSchema{
		{field},
		{field, anotherField},
	}
	for _, tc := range tcs {
		td := tableDef{
			datasetID: datasetID,
			tableID:   tableID,
			toUpdate: bigquery.TableMetadataToUpdate{
				Schema: bigquery.Schema(tc),
			},
		}
		err := updateFromTableDef(ctx, ts, td)
		if err != nil {
			t.Fatal(err)
		}
		got, err := ts.getTableMetadata(ctx, datasetID, tableID)
		if err != nil {
			t.Fatal(err)
		}
		want := &bigquery.TableMetadata{Schema: bigquery.Schema(tc)}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("got: %v; want: %v", got, want)
		}
	}
}
