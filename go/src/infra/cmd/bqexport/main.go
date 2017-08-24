// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// bqexport loads a BigQuery struct definition from Go source and exports a
// table definition protobuf suitable for "bqschemaupdater" to instantiate and
// process.
//
// https://github.com/GoogleCloudPlatform/google-cloud-go/issues/726
//
// The "d=" tag instructs "bqexport" to read the remainder of the tag as a
// field description.
//
package main

import (
	"flag"
	"fmt"
	"go/build"
	"os"
	"path/filepath"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging/gologger"

	"golang.org/x/net/context"
)

var (
	path = flag.String("path", "", "Path to the TableDef protobuf to import (required).")
	name = flag.String("name", "", "Name of the output struct and file. If empty, will be derived from TableDef.")
	dest = flag.String("dest", "", "Path to the destination directory. If empty, current working directory will be used.")
)

func mainImpl(c context.Context) error {
	flag.Parse()

	if *path == "" {
		return errors.Reason("no TableDef protobuf path was specified (-path)").Err()
	}

	if *dest == "" {
		var err error
		if *dest, err = os.Getwd(); err != nil {
			return errors.Annotate(err, "failed to get current working directory").Err()
		}
	}

	pkg, err := build.Default.ImportDir(*dest, 0)
	if err != nil {
		return errors.Annotate(err, "failed to import destination package from: %q", dest).Err()
	}

	td, err := LoadTableDef(*path)
	if err != nil {
		return errors.Annotate(err, "failed to load table def").Err()
	}

	if *name == "" {
		*name = td.TableId
	}

	outName := fmt.Sprintf("%s.gen.go", camelCaseToUnderscore(*name))
	outPath := filepath.Join(*dest, outName)
	return Export(c, td, pkg.Name, toCamelCase(*name), outPath)
}

func main() {
	c := context.Background()
	c = gologger.StdConfig.Use(c)

	if err := mainImpl(c); err != nil {
		errors.Log(c, err)
		os.Exit(1)
	}
}
