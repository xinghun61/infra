// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tabledef

import (
	"reflect"
	"testing"

	"cloud.google.com/go/bigquery"
)

func TestBQSchema(t *testing.T) {
	f := []*FieldSchema{
		{
			Name:        "test_field",
			Description: "test description",
			Type:        Type_STRING,
			IsRepeated:  true,
		},
	}
	got := BQSchema(f)
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
	f := &FieldSchema{
		Name:        "test_field",
		Description: "test description",
		Type:        Type_RECORD,
		IsRepeated:  true,
		Schema: []*FieldSchema{
			{
				Name:        "nested_field",
				Description: "i am nested",
				Type:        Type_STRING,
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
