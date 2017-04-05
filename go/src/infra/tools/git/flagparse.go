// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"strings"
)

// FlagSplitterDef is the definition for a compiled FlagSplitter.
type FlagSplitterDef struct {
	// Solitary is the list of strings that identify as flags with no additional
	// arguments.
	//
	// For example:
	// --flag value
	Solitary []string

	// WithArg is the list of strings that identify as flags and always have an
	// additional argument.
	//
	// For example:
	// --flag value
	WithArg []string

	// WithArgAllowConjoined is a special case of TwoArgs that is allowed to
	// either have one additional argument or be joined to an additional argument
	// via an "=".
	//
	// For example:
	// --flag value
	// --flag=value
	WithArgAllowConjoined []string
}

// Compile compiles d into a FlagSplitter.
func (d FlagSplitterDef) Compile() FlagSplitter {
	// Compile our total flag set into a quick lookup map.
	fs := make(FlagSplitter, len(d.Solitary)+len(d.WithArg)+len(d.WithArgAllowConjoined))
	fs.registerFlags(d.Solitary, flagSplitterFlag{NumArgs: 0, AllowConjoined: false})
	fs.registerFlags(d.WithArg, flagSplitterFlag{NumArgs: 1, AllowConjoined: false})
	fs.registerFlags(d.WithArgAllowConjoined, flagSplitterFlag{NumArgs: 1, AllowConjoined: true})
	return fs
}

// flagSplitterFlag is a flag definition for FlagSplitter.
type flagSplitterFlag struct {
	NumArgs        int
	AllowConjoined bool
}

// FlagSplitter contains a compiled mapping of command-line flags and their
// handling details. It is used via Parse to split a set of command-line
// argument.
type FlagSplitter map[string]flagSplitterFlag

func (fs FlagSplitter) registerFlags(flags []string, fsf flagSplitterFlag) {
	for _, v := range flags {
		fs[v] = fsf
	}
}

// Split parses a set of command-line arguments into recognized flags and an
// unrecognized remainder, extra.
func (fs FlagSplitter) Split(args []string) (flags, extra []string) {
	pos := fs.findFirstNonFlag(args)
	flags, extra = args[:pos], args[pos:]
	return
}

func (fs FlagSplitter) findFirstNonFlag(args []string) (pos int) {
	// Iterate through args and classify.
	for pos < len(args) {
		flag := args[pos]
		if !strings.HasPrefix(flag, "-") {
			// Not a flag. Everything is "extra".
			return
		}

		// If there is an "=" in the flag, then this is a joint two-argument flag.
		conjoinedArg := false
		if idx := strings.IndexRune(flag, '='); idx > 0 {
			flag, conjoinedArg = flag[:idx], true
		}
		fsf, ok := fs[flag]
		switch {
		case !ok:
			// Unrecognized flag.
			return

		case conjoinedArg && !fsf.AllowConjoined:
			// If this flag has an argument, but does not allow "=", then treat it as
			// an unrecognized flag.
			return
		}

		switch count := fsf.NumArgs; count {
		case 0:
			pos++

		case 1:
			if !conjoinedArg {
				pos++
			}
			pos++

		default:
			panic("don't support more than two arguments")
		}

		if pos > len(args) {
			// This can happen with a multi-part flag that is missing its additional
			// parts.
			pos = len(args)
			return
		}
	}

	return
}
