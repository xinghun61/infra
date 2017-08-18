// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"go/build"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"text/template"
	"unicode"

	"go.chromium.org/luci/common/errors"

	"golang.org/x/net/context"
)

var loaderTmpl = template.Must(template.New("").Parse(`
package main

import "infra/cmd/bqexport/util"
import pkg "{{.SourcePackage}}"

func main() {
	exp := util.Exporter{
		TableDef: &pkg.{{.TableDefName}},
		Schema: &pkg.{{.StructName}}{},
	}
	exp.Main()
}`))

func withTempDir(fn func(string) error) error {
	tdir, err := ioutil.TempDir("", "bqexport")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tdir)
	return fn(tdir)
}

// Exporter exports a BigQuery schema from a Go structure in the named source.
type Exporter struct {
	Package  string
	Name     string
	TableDef string
	OutDir   string
}

// Export writes the BigQuery schema JSON to the specified output file.
func (e *Exporter) Export(c context.Context, fileName string) error {
	srcDir := ""

	switch {
	case e.Name == "":
		return errors.New("you must supply a name (-name)")
	case e.OutDir == "":
		return errors.New("an output directory is required (-outdir)")
	}

	pkg := e.Package
	if pkg == "" {
		var err error
		if srcDir, err = os.Getwd(); err != nil {
			return errors.Annotate(err, "could not get working directory").Err()
		}
		pkg = "."
	}

	tableDef := e.TableDef
	if tableDef == "" {
		tableDef = e.Name + "Table"
	}

	p, err := build.Import(pkg, srcDir, 0)
	if err != nil {
		return errors.Annotate(err, "could not import package at %q", pkg).Err()
	}

	// Automatically generate the JSON filename, if one isn't provided.
	if fileName == "" {
		fileName = fmt.Sprintf("%s_%s.json", p.Name, camelCaseToUnderscore(tableDef))
	}

	return withTempDir(func(tdir string) error {
		return generateAndRunExtractor(c, tdir, e.OutDir, fileName, p.ImportPath, e.Name, tableDef)
	})
}

func generateAndRunExtractor(c context.Context, tdir, outDir, fileName, importPath, name, tableDef string) error {
	// Emit our "main.go".
	mainPath := filepath.Join(tdir, "main.go")
	fd, err := os.Create(mainPath)
	if err != nil {
		return errors.Annotate(err, "could not create main.go at %q", mainPath).Err()
	}
	err = loaderTmpl.Execute(fd, struct {
		SourcePackage string
		StructName    string
		TableDefName  string
	}{importPath, name, tableDef})
	if err != nil {
		fd.Close()
		return errors.Annotate(err, "could not generate main.go").Err()
	}
	if err := fd.Close(); err != nil {
		return errors.Annotate(err, "could not Close main.go").Err()
	}

	// Run it.
	cmd := exec.CommandContext(c, "go", "run", mainPath, "-dir", outDir, "-name", fileName)
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return errors.Annotate(err, "could not run command").Err()
	}
	return nil
}

// camelCaseToUnderscore converts a camel-case string to a lowercase string
// with underscore delimiters.
func camelCaseToUnderscore(v string) string {
	var parts []string
	var segment []rune
	addSegment := func() {
		if len(segment) > 0 {
			parts = append(parts, string(segment))
			segment = segment[:0]
		}
	}

	for _, r := range v {
		if unicode.IsUpper(r) {
			addSegment()
		}
		segment = append(segment, unicode.ToLower(r))
	}
	addSegment()
	return strings.Join(parts, "_")
}
