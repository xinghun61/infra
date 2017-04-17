// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"strings"

	"github.com/luci/luci-go/common/errors"
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

// ParsedFlags is the output of a FlagSplitter's Split function.
type ParsedFlags struct {
	// Flags is the set of parsed flags. Flags with arguments will have those
	// argument as values.
	Flags map[string]string

	// Pos are identified positional arguments.
	Pos []string

	// Extra is flag data that could not be otherwise categorized. When flags
	// don't match expected, we stop parsing and fill Extra with the remainder,
	// since we can't otherwise know what to do with them.
	Extra []string
}

func (fs FlagSplitter) registerFlags(flags []string, fsf flagSplitterFlag) {
	for _, v := range flags {
		fs[v] = fsf
	}
}

// Split parses a set of command-line arguments into recognized flags and an
// unrecognized remainder, extra.
func (fs FlagSplitter) Split(args []string, stopAtFirstPositional bool) (pf ParsedFlags) {
	for len(args) > 0 {
		arg := args[0]
		if !strings.HasPrefix(arg, "-") {
			// Not a flag.
			if stopAtFirstPositional {
				pf.Pos = append(pf.Pos, args...)
				return
			}

			// Single unknown positional argument, consume and resume parsing.
			pf.Pos = append(pf.Pos, arg)
			args = args[1:]
			continue
		}

		// Hard separator.
		if arg == "--" {
			pf.Pos = append(pf.Pos, args[1:]...)
			return
		}

		// If there is an "=" in the arg, then this is a conjoined flag. Store the
		// conjoined part in "flagArg".
		flagArg := ""
		if idx := strings.IndexRune(arg, '='); idx > 0 {
			arg, flagArg = arg[:idx], arg[idx+len("="):]
		}

		fsf, ok := fs[arg]
		if !ok || flagArg != "" && !fsf.AllowConjoined {
			// Either:
			// - Not a known flag, so consider it (and everything following it) an
			//   extra argument.
			// - Encountered a conjoined argument, but this type of argument is not
			//   allowed to be conjoined.
			//
			// We don't know how to handle this flag, so throw it all in "Extra".
			pf.Extra = args
			return
		}

		switch fsf.NumArgs {
		case 0:
			args = args[1:]

		case 1:
			switch {
			case flagArg != "":
				args = args[1:] // Conjoined
			case len(args) >= 2:
				flagArg = args[1]
				args = args[2:]
			default:
				// Two-argument flag, but only one argument available. Dump the rest
				// into "Extra".
				pf.Extra = args
				return
			}

		default:
			panic(errors.Reason("don't know how to handle flag (%(flag)s) with more than one arg").
				D("flag", arg).
				Err())
		}

		if pf.Flags == nil {
			pf.Flags = make(map[string]string, len(args))
		}
		pf.Flags[arg] = flagArg
	}

	return
}
