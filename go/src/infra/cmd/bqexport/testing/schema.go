// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testing

import (
	"fmt"

	"infra/libs/bqschema/tabledef"

	"cloud.google.com/go/bigquery"
)

// TestSchemaTable is a schema table used for testing.
var TestSchemaTable = tabledef.TableDef{
	Dataset:                    tabledef.TableDef_RAW_EVENTS,
	Description:                "Table Def Description",
	TableId:                    "table-id",
	Name:                       "Friendly Name",
	PartitionTable:             true,
	PartitionExpirationSeconds: 1337,
	Fields: []*tabledef.FieldSchema{
		{
			Name:        "A",
			Description: "The letter 'A'.",
			Type:        tabledef.Type_STRING,
		},
		{
			Name:        "B",
			Description: "The letter 'B'.",
			Type:        tabledef.Type_INTEGER,
		},
		{
			Name:        "C",
			Description: "The letter 'C'.",
			Type:        tabledef.Type_FLOAT,
		},

		{
			Name:        "Desc",
			Description: "This is a description string.\nIt has a newline.",
			Type:        tabledef.Type_STRING,
			IsRequired:  true,
		},

		{
			Name:       "Req",
			Type:       tabledef.Type_STRING,
			IsRequired: true,
		},

		{
			Name: "legacy_date_time",
			Type: tabledef.Type_DATETIME,
		},

		{
			Name:       "Rec",
			Type:       tabledef.Type_RECORD,
			IsRepeated: true,
			Schema: []*tabledef.FieldSchema{
				{
					Name:        "optional_field",
					Description: "This is an optional field.",
					Type:        tabledef.Type_STRING,
				},

				{
					Name:       "required_field",
					Type:       tabledef.Type_STRING,
					IsRequired: true,
				},
			},
		},
	},
}

// SchemaToProto converts a BigQuery Schema to a slice of FieldSchema protobufs.
func SchemaToProto(schema bigquery.Schema) []*tabledef.FieldSchema {
	pbs := make([]*tabledef.FieldSchema, len(schema))
	for i, field := range schema {
		pbs[i] = SchemaFieldToProto(field)
	}
	return pbs
}

// SchemaFieldToProto converts a single BigQuery FieldSchema value to a
// FieldSchema protobuf.
func SchemaFieldToProto(field *bigquery.FieldSchema) *tabledef.FieldSchema {
	fs := tabledef.FieldSchema{
		Name:        field.Name,
		Description: field.Description,
		IsRepeated:  field.Repeated,
		IsRequired:  field.Required,
	}

	switch field.Type {
	case bigquery.StringFieldType:
		fs.Type = tabledef.Type_STRING
	case bigquery.BytesFieldType:
		fs.Type = tabledef.Type_BYTES
	case bigquery.IntegerFieldType:
		fs.Type = tabledef.Type_INTEGER
	case bigquery.FloatFieldType:
		fs.Type = tabledef.Type_FLOAT
	case bigquery.BooleanFieldType:
		fs.Type = tabledef.Type_BOOLEAN
	case bigquery.TimestampFieldType:
		fs.Type = tabledef.Type_TIMESTAMP
	case bigquery.RecordFieldType:
		fs.Type = tabledef.Type_RECORD
		fs.Schema = SchemaToProto(field.Schema)
	case bigquery.DateFieldType:
		fs.Type = tabledef.Type_DATE
	case bigquery.TimeFieldType:
		fs.Type = tabledef.Type_TIME
	case bigquery.DateTimeFieldType:
		fs.Type = tabledef.Type_DATETIME
	default:
		panic(fmt.Errorf("unknown field type: %v", field.Type))
	}

	return &fs
}

// NormalizeToInferredSchema normalizes FieldSchema protobuf to the output
// produced by bigquery.InferSchema.
func NormalizeToInferredSchema(schema []*tabledef.FieldSchema) {
	for _, field := range schema {
		field.IsRequired = !field.IsRepeated
		field.Description = ""

		if field.Schema != nil {
			NormalizeToInferredSchema(field.Schema)
		}
	}
}
