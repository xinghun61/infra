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

	// SolitaryAllowConjoined is the list of strings that identify as flags with
	// either no additional arguments or one conjoined argument.
	//
	// For example:
	// --flag
	// --flag=value
	SolitaryAllowConjoined []string

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
	fs.registerFlags(d.SolitaryAllowConjoined, flagSplitterFlag{NumArgs: 0, AllowConjoined: true})
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
func (fs FlagSplitter) Split(args []string, stopAtFirstPositional bool) (flags, pos, extra []string) {
	// Like "append", but allocates capacity of "args" on first addition to
	// minimize reallocations during parsing.
	augment := func(v []string, values ...string) []string {
		if v == nil {
			v = make([]string, 0, len(args))
		}
		return append(v, values...)
	}

	for len(args) > 0 {
		arg := args[0]
		if !strings.HasPrefix(arg, "-") {
			// Not a flag.
			if stopAtFirstPositional {
				pos = augment(pos, args...)
				return
			}

			// Single unknown positional argument, consume and resume parsing.
			pos = augment(pos, arg)
			args = args[1:]
			continue
		}

		// Hard separator.
		if arg == "--" {
			pos = augment(pos, args[1:]...)
			return
		}

		// If there is an "=" in the arg, then this is a joint two-argument flag.
		conjoinedArg := false
		if idx := strings.IndexRune(arg, '='); idx > 0 {
			arg, conjoinedArg = arg[:idx], true
		}
		fsf, ok := fs[arg]
		switch {
		case !ok:
			// Not a known flag, so consider it (and everything following it) an
			// extra argument.
			extra = args
			return

		case conjoinedArg && !fsf.AllowConjoined:
			// If this flag has an argument, but does not allow "=", then treat it as
			// an unrecognized flag and return it (and remainder) as extra.
			extra = args
			return
		}

		consume := fsf.NumArgs + 1
		if consume > 1 && conjoinedArg {
			consume--
		}
		if consume > len(args) {
			// This can happen with a multi-part flag that is missing its additional
			// parts.
			extra = args
			return
		}
		flags = augment(flags, args[:consume]...)
		args = args[consume:]
	}

	return
}
