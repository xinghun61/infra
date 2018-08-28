// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package log provides custom logging for Lucifer.

This package is compatible with and is a superset of the standard log
package.
*/
package log

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
)

// Setup sets up logging configuration.
func Setup() {
	log.SetPrefix(fmt.Sprintf("%s: ", filepath.Base(os.Args[0])))
}

// Constants copied from the standard log package for compatibility.
const (
	Ldate         = log.Ldate
	Ltime         = log.Ltime
	Lmicroseconds = log.Lmicroseconds
	Llongfile     = log.Llongfile
	Lshortfile    = log.Lshortfile
	LUTC          = log.LUTC
	LstdFlags     = log.LstdFlags
)

// Functions copied from the standard log package for compatibility.
var (
	Fatal     = log.Fatal
	Fatalf    = log.Fatalf
	Fatalln   = log.Fatalln
	Flags     = log.Flags
	Output    = log.Output
	Panic     = log.Panic
	Panicf    = log.Panicf
	Panicln   = log.Panicln
	Prefix    = log.Prefix
	Print     = log.Print
	Printf    = log.Printf
	Println   = log.Println
	SetFlags  = log.SetFlags
	SetOutput = log.SetOutput
	SetPrefix = log.SetPrefix
)

// Logger is copied from the standard log package for compatibility.
type Logger = log.Logger
