// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// bqexport loads a BigQuery struct definition from Go source and exports a
// table definition protobuf suitable for "bqschemaupdater" to instantiate and
// process.
//
// This generator can be used to enable a BigQuery Go struct to be the canonical
// definition of a BigQuery table.
//
// Example usage:
//
//	go:generate bqexportschema -name MySchemaStruct
//
// "bqexport" supports an additional struct tag:
//
//	type MySchema struct {
//		OptionalField string `bigquery:"optional" bqexport:"d=optional field"`
//		RequiredField string `bigquery:"required" bqexport:"req,d=required field"`
//	}
//
// The "req" tag instructs "bqexport" to mark that field required. By default,
// all fields are optional. Ideally this would be supported directly by the
// BigQuery package, see:
//
// https://github.com/GoogleCloudPlatform/google-cloud-go/issues/726
//
// The "d=" tag instructs "bqexport" to read the remainder of the tag as a
// field description.
//
package main

import (
	"flag"
	"os"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging/gologger"

	"golang.org/x/net/context"
)

var (
	pkg      = flag.String("package", "", "Name of the package to import from. If empty, use current working directory.")
	name     = flag.String("name", "", "(Required) Name of the struct within 'package' to export.")
	tableDef = flag.String("table-def-name", "", "Name of the table definition within 'package'. If empty, use <name>Table.")
	outDir   = flag.String("out-dir", "",
		"(Required) Path to the root output directory. The JSON file will be written to a subdirectory based on its dataset.")
	outName = flag.String("out-name", "", "Output JSON filename. If empty, one will be derived from -name.")
)

func main() {
	flag.Parse()
	exp := Exporter{
		Package:  *pkg,
		Name:     *name,
		TableDef: *tableDef,
		OutDir:   *outDir,
	}

	c := context.Background()
	c = gologger.StdConfig.Use(c)

	if err := exp.Export(c, *outName); err != nil {
		errors.Log(c, err)
		os.Exit(1)
	}
}
