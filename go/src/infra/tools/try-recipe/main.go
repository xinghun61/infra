// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"flag"
	"os"
	"os/signal"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/data/rand/mathrand"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"

	"github.com/maruel/subcommands"
)

type globalConfig struct {
	logConfig *log.Config
}

type wrappedCommandRun struct {
	run func(a subcommands.Application, args []string, env subcommands.Env) int
	fs  *flag.FlagSet
}

func (wr wrappedCommandRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	return wr.run(a, args, env)
}

func (wr wrappedCommandRun) GetFlags() *flag.FlagSet {
	return wr.fs
}

func (g *globalConfig) wrapCommands(s ...*subcommands.Command) []*subcommands.Command {
	for i, cmd := range s {
		cr := cmd.CommandRun()
		run := cr.Run
		fs := cr.GetFlags()
		g.logConfig.AddFlags(fs)

		s[i].CommandRun = func() subcommands.CommandRun {
			return wrappedCommandRun{run, fs}
		}
	}
	return s
}

func handleInterruption(ctx context.Context) context.Context {
	ctx, cancel := context.WithCancel(ctx)
	signalC := make(chan os.Signal)
	signal.Notify(signalC, os.Interrupt)
	go func() {
		interrupted := false
		for range signalC {
			if interrupted {
				os.Exit(1)
			}
			interrupted = true
			cancel()
		}
	}()
	return ctx
}

func main() {
	mathrand.SeedRandomly()

	cfg := globalConfig{
		&log.Config{Level: log.Info},
	}

	var application = cli.Application{
		Name:  "try-recipe",
		Title: "Launches recipes into the cloud.",

		Context: func(ctx context.Context) context.Context {
			goLoggerCfg := gologger.LoggerConfig{Out: os.Stderr}
			goLoggerCfg.Format = "[%{level:.1s} %{time:2006-01-02 15:04:05}] %{message}"
			ctx = goLoggerCfg.Use(ctx)
			ctx = cfg.logConfig.Set(ctx)
			return handleInterruption(ctx)
		},

		Commands: cfg.wrapCommands(
			subcommandIsolate,

			// TODO(iannucci): add auth subcommands

			subcommands.CmdHelp,
		),
	}

	os.Exit(subcommands.Run(&application, nil))
}
