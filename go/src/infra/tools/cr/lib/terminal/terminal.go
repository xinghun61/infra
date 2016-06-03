// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package terminal provides utilities for printing to and reading user input
// from an interactive terminal.
package terminal

import (
	"bufio"
	"fmt"
	"os"
)

// ShowDebug controls whether or not calls to terminal.Debug produce output.
var ShowDebug = false

// Print prints the given format string (and arguments) to standard out.
func Print(format string, args ...interface{}) {
	fmt.Println(fmt.Sprintf(format, args...))
}

// Debug is the same as Print, but only produces output if ShowDebug is true.
func Debug(format string, args ...interface{}) {
	if ShowDebug {
		fmt.Println(fmt.Sprintf(format, args...))
	}
}

// Prompt prints a string to standard out, then waits for a single line
// of user input and returns it.
func Prompt(prompt string) (string, error) {
	fmt.Print(prompt)
	reader := bufio.NewReader(os.Stdin)
	return reader.ReadString('\n')
}
