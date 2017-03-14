// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package subcommand

import (
	"errors"
	"flag"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestNew(t *testing.T) {
	t.Parallel()
	Convey("When creating new subcommands", t, func() {
		reg := &registry{make(map[string]*Subcommand)}

		Convey("you can register one command", func() {
			first := reg.new("first", "foo", "foofoo", nil, nil)
			So(first, ShouldNotBeNil)
			So(len(reg.subcommands), ShouldEqual, 1)

			Convey("and you can register a second command with a different name", func() {
				second := reg.new("second", "bar", "barbar", nil, nil)
				So(second, ShouldNotBeNil)
				So(len(reg.subcommands), ShouldEqual, 2)
			})

			Convey("but you cannot register two commands with the same name", func() {
				So(func() { reg.new("first", "bar", "barbar", nil, nil) }, ShouldPanic)
			})
		})
	})
}

func TestGet(t *testing.T) {
	t.Parallel()
	Convey("When retrieving a subcommand", t, func() {
		reg := &registry{make(map[string]*Subcommand)}
		cmd := reg.new("cmd", "short", "long", nil, nil)

		Convey("unknown names result in nil", func() {
			So(reg.get("test"), ShouldBeNil)
		})

		Convey("recognized names should be identical to initial object", func() {
			So(reg.get("cmd"), ShouldResemble, cmd)
		})
	})
}

func TestInitFlags(t *testing.T) {
	t.Parallel()
	Convey("When collecting flags from subcommands", t, func() {
		reg := &registry{make(map[string]*Subcommand)}
		flags := flag.NewFlagSet("flags", flag.ContinueOnError)

		Convey("nil flag functions work fine", func() {
			cmd := reg.new("cmd", "short", "long", nil, nil)
			cmd.InitFlags(flags)
			flagCount := 0
			flags.VisitAll(func(f *flag.Flag) { flagCount++ })
			So(flagCount, ShouldEqual, 0)
		})

		Convey("if new flags are defined", func() {
			// Define the flag function for the command.
			flagFn := func(f *flag.FlagSet) {
				f.String("number", "one", "a numeric string")
				f.Float64("pie", 3.14, "pi")
			}
			cmd := reg.new("cmd", "short", "long", flagFn, nil)

			Convey("pre-existing flags are left untouched", func() {
				flags.Bool("really", false, "really do it")
				cmd.InitFlags(flags)
				So(flags.Lookup("really"), ShouldNotBeNil)
			})

			Convey("new flags are successfully added", func() {
				cmd.InitFlags(flags)
				So(flags.Lookup("pie"), ShouldNotBeNil)
			})

			Convey("duplicate flags are disallowed", func() {
				flags.Int("number", 1, "an int")
				So(func() { cmd.InitFlags(flags) }, ShouldPanic)
			})
		})
	})
}

func TestRun(t *testing.T) {
	t.Parallel()
	Convey("When running a subcommand", t, func() {
		reg := &registry{make(map[string]*Subcommand)}
		flags := flag.NewFlagSet("flags", flag.ContinueOnError)

		Convey("nil run functions return nil", func() {
			cmd := reg.new("cmd", "short", "long", nil, nil)
			So(cmd.Run(flags), ShouldBeNil)
		})

		Convey("success is propagated", func() {
			cmd := reg.new("cmd", "short", "long", nil, func(f *flag.FlagSet) error { return nil })
			So(cmd.Run(flags), ShouldBeNil)
		})

		Convey("errors are propagated", func() {
			err := errors.New("an error")
			cmd := reg.new("cmd", "short", "long", nil, func(f *flag.FlagSet) error { return err })
			So(cmd.Run(flags), ShouldEqual, err)
		})
	})
}

func ExampleSubcommand_Help() {
	reg := &registry{make(map[string]*Subcommand)}
	cmd := reg.new("test", "short", "long", nil, nil)
	flags := flag.NewFlagSet("test", flag.ContinueOnError)
	cmd.Help(flags)
	// Output:
	// short
	//
	// long
}

func ExampleTabulate() {
	reg := &registry{make(map[string]*Subcommand)}
	_ = reg.new("first", "foo", "foofoo", nil, nil)
	_ = reg.new("second", "bar", "barbar", nil, nil)
	reg.tabulate()
	// Output:
	//   first   foo
	//   second  bar
}
