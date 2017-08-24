// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"log"

	"infra/cmd/bqexport/testing"
	"infra/libs/bqschema/tabledef"

	"github.com/golang/protobuf/proto"

	"cloud.google.com/go/bigquery"
)

func main() {
	log.Println("Testing generated data...")

	bqSchema, err := bigquery.InferSchema(&TestSchema{})
	if err != nil {
		log.Fatalf("could not infer schema: %s", err)
	}

	convertBQSchema := testing.TestSchemaTable
	convertBQSchema.Fields = testing.SchemaToProto(bqSchema)

	tst := proto.Clone(&testing.TestSchemaTable).(*tabledef.TableDef)
	testing.NormalizeToInferredSchema(tst.Fields)

	if !proto.Equal(&convertBQSchema, tst) {
		log.Println("Original:")
		log.Println(proto.MarshalTextString(tst))

		log.Println("Converted:")
		log.Println(proto.MarshalTextString(&convertBQSchema))

		log.Fatalln("Converted schema does not match.")
	}

	log.Println("Test successful!")
}
