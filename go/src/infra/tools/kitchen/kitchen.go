// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"bytes"
	"flag"
	"fmt"
	"os"
	"os/signal"

	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/data/rand/mathrand"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
)

var logConfig = log.Config{
	Level: log.Info,
}

var application = cli.Application{
	Name:  "kitchen",
	Title: "Kitchen. It can run a recipe.",
	Context: func(ctx context.Context) context.Context {
		cfg := gologger.StdConfig
		cfg.Format = "[%{level:.1s} %{time:2006-01-02 15:04:05}] %{message}"
		ctx = cfg.Use(ctx)
		ctx = logConfig.Set(ctx)
		return handleInterruption(ctx)
	},
	Commands: []*subcommands.Command{
		subcommands.CmdHelp,
		cmdCook,
	},
}

func main() {
	mathrand.SeedRandomly()

	logConfig.AddFlags(flag.CommandLine)
	flag.Parse()

	os.Exit(subcommands.Run(&application, flag.Args()))
}

// handleInterruption cancels the context on first SIGTERM and
// exits the process on a second SIGTERM.
func handleInterruption(ctx context.Context) context.Context {
	ctx, cancel := context.WithCancel(ctx)
	signalC := make(chan os.Signal)
	signal.Notify(signalC, os.Interrupt)
	go func() {
		<-signalC
		cancel()
		<-signalC
		os.Exit(1)
	}()
	return ctx
}

// logAnnotatedErr logs the full stack trace from an annotated error to the
// installed logger at error level.
func logAnnotatedErr(ctx context.Context, err error) {
	if err == nil {
		return
	}

	var buf bytes.Buffer
	if _, derr := errors.RenderStack(err).DumpTo(&buf); derr != nil {
		// This can't really fail, since we're rendering to a Buffer.
		panic(derr)
	}

	log.Errorf(ctx, "Annotated error stack:\n%s", buf.String())
}

type InputError string

func (e InputError) Error() string { return string(e) }

// inputError returns an error that will be printed to stderr without a stack
// trace.
func inputError(format string, args ...interface{}) error {
	// We don't use D to keep signature of this function simple
	// and to keep UserError as a leaf.
	return errors.Annotate(InputError(fmt.Sprintf(format, args...))).Err()
}
