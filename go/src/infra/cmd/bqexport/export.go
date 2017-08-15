// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
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
}

// Export writes the BigQuery schema JSON to the specified output file.
func (e *Exporter) Export(c context.Context, out string) error {
	srcDir := ""

	flag.Parse()

	name := e.Name
	if name == "" {
		return errors.New("you must supply a name (-name)")
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
		tableDef = name + "Table"
	}

	if out == "" {
		out = fmt.Sprintf("bq_%s.json", strings.Map(func(r rune) rune {
			if unicode.IsLetter(r) && r <= unicode.MaxASCII {
				return unicode.ToLower(r)
			}
			return -1
		}, tableDef))
	} else {
		out = filepath.FromSlash(out)
	}

	p, err := build.Import(pkg, srcDir, build.FindOnly)
	if err != nil {
		return errors.Annotate(err, "could not import package at %q", pkg).Err()
	}

	return withTempDir(func(tdir string) error {
		return generateAndRunExtractor(c, tdir, out, p.ImportPath, name, tableDef)
	})
}

func generateAndRunExtractor(c context.Context, tdir, out, importPath, name, tableDef string) error {
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

	// Open our output file.
	outFd, err := os.Create(out)
	if err != nil {
		return errors.Annotate(err, "could not create output file: %s", out).Err()
	}

	// Run it.
	cmd := exec.CommandContext(c, "go", "run", mainPath)
	cmd.Stdout = outFd
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		outFd.Close()
		return errors.Annotate(err, "could not run command").Err()
	}

	if err := outFd.Close(); err != nil {
		return errors.Annotate(err, "could not close output file").Err()
	}
	return nil
}
