// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tabledef

import (
	"fmt"

	"cloud.google.com/go/bigquery"
)

// BQSchema constructs a bigquery.Schema from a []*TableDef.FieldSchema
func BQSchema(fields []*FieldSchema) bigquery.Schema {
	if len(fields) == 0 {
		return nil
	}

	s := make(bigquery.Schema, len(fields))
	for i, f := range fields {
		s[i] = bqField(f)
	}
	return s
}

func bqField(f *FieldSchema) *bigquery.FieldSchema {
	fs := &bigquery.FieldSchema{
		Name:        f.Name,
		Description: f.Description,
		Type:        tdTypeToBQType(f.Type),
		Repeated:    f.IsRepeated,
		Required:    f.IsRequired,
	}
	if fs.Type == bigquery.RecordFieldType {
		fs.Schema = BQSchema(f.Schema)
	}
	return fs
}

func tdTypeToBQType(t Type) bigquery.FieldType {
	switch t {
	case Type_STRING:
		return bigquery.StringFieldType
	case Type_BYTES:
		return bigquery.BytesFieldType
	case Type_INTEGER:
		return bigquery.IntegerFieldType
	case Type_FLOAT:
		return bigquery.FloatFieldType
	case Type_BOOLEAN:
		return bigquery.BooleanFieldType
	case Type_TIMESTAMP:
		return bigquery.TimestampFieldType
	case Type_RECORD:
		return bigquery.RecordFieldType
	case Type_DATE:
		return bigquery.DateFieldType
	case Type_TIME:
		return bigquery.TimeFieldType
	case Type_DATETIME:
		return bigquery.DateTimeFieldType
	default:
		panic(fmt.Errorf("unknown field type: %s", t.String()))
	}
}
