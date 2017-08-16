// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testing

import (
	"infra/libs/bqschema/tabledef"
)

// TestSchemaTable is the TableDef associated with TestSchema.
var TestSchemaTable = tabledef.TableDef{
	DatasetId:                  "dataset-id",
	Description:                "Table Def Description",
	TableId:                    "table-id",
	Name:                       "Friendly Name",
	PartitionTable:             true,
	PartitionExpirationSeconds: 1337,
}

// TestSchema is the BigQuery schema struct used in generation testing.
type TestSchema struct {
	A string
	B int64
	C float64

	Desc string `bqexport:"req,d=This is a description string"`
	Req  string `bqexport:"req"`

	Rec []TestRecord
}

// TestRecord is a record within TestSchema.
type TestRecord struct {
	Optional string `bigquery:"optional_field"`
	Required string `bigquery:"required_field" bqexport:"req"`
}
