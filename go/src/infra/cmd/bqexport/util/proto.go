// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package util

import (
	"fmt"

	pb "infra/libs/bqschema/tabledef"

	"cloud.google.com/go/bigquery"
)

// SchemaToProto converts a BigQuery Schema to a slice of FieldSchema protobufs.
func SchemaToProto(schema bigquery.Schema) []*pb.FieldSchema {
	pbs := make([]*pb.FieldSchema, len(schema))
	for i, field := range schema {
		pbs[i] = SchemaFieldToProto(field)
	}
	return pbs
}

// SchemaFieldToProto converts a single BigQuery FieldSchema value to a
// FieldSchema protobuf.
func SchemaFieldToProto(field *bigquery.FieldSchema) *pb.FieldSchema {
	fs := pb.FieldSchema{
		Name:        field.Name,
		Description: field.Description,
		IsRepeated:  field.Repeated,
		IsRequired:  field.Required,
	}

	switch field.Type {
	case bigquery.StringFieldType:
		fs.Type = pb.Type_STRING
	case bigquery.BytesFieldType:
		fs.Type = pb.Type_BYTES
	case bigquery.IntegerFieldType:
		fs.Type = pb.Type_INTEGER
	case bigquery.FloatFieldType:
		fs.Type = pb.Type_FLOAT
	case bigquery.BooleanFieldType:
		fs.Type = pb.Type_BOOLEAN
	case bigquery.TimestampFieldType:
		fs.Type = pb.Type_TIMESTAMP
	case bigquery.RecordFieldType:
		fs.Type = pb.Type_RECORD
		fs.Schema = SchemaToProto(field.Schema)
	case bigquery.DateFieldType:
		fs.Type = pb.Type_DATE
	case bigquery.TimeFieldType:
		fs.Type = pb.Type_TIME
	case bigquery.DateTimeFieldType:
		fs.Type = pb.Type_DATETIME
	default:
		panic(fmt.Errorf("unknown field type: %v", field.Type))
	}

	return &fs
}
