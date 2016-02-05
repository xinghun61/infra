// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"runtime"
	"strings"
	"time"

	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/common/tsmon"
	"github.com/maruel/subcommands"
	gol "github.com/op/go-logging"
	"golang.org/x/net/context"

	"infra/libs/cipd"
	"infra/tools/cloudtail"
)

var authOptions = auth.Options{
	Logger:                 gologger.New(os.Stderr, gol.INFO),
	ServiceAccountJSONPath: defaultServiceAccountJSONPath(),
	Scopes: []string{
		auth.OAuthScopeEmail,
		"https://www.googleapis.com/auth/logging.write",
	},
}

// Where to look for service account JSON creds if not provided via CLI.
const (
	defaultServiceAccountPosix = "/creds/service_accounts/service-account-cloudtail.json"
	defaultServiceAccountWin   = "C:\\creds\\service_accounts\\service-account-cloudtail.json"
)

////////////////////////////////////////////////////////////////////////////////
// Common functions and structs.

type commonOptions struct {
	authFlags     authcli.Flags
	tsmonFlags    tsmon.Flags
	localLogLevel logging.Level
	debug         bool

	projectID    string
	resourceType string
	resourceID   string
	logID        string
}

type state struct {
	context context.Context
	client  cloudtail.Client
	buffer  cloudtail.PushBuffer
}

// registerFlags adds all CLI flags to the flag set.
func (opts *commonOptions) registerFlags(f *flag.FlagSet, defaultAutoFlush bool) {
	// Default log level.
	opts.localLogLevel = logging.Warning

	opts.authFlags.Register(f, authOptions)
	f.Var(&opts.localLogLevel, "local-log-level",
		"The logging level of local logger (for cloudtail own logs): debug, info, warning, error")
	f.BoolVar(&opts.debug, "debug", false,
		"If set, will print Cloud Logging calls to stdout instead of sending them")

	f.StringVar(&opts.projectID, "project-id", "", "Cloud project ID to push logs to")
	f.StringVar(&opts.resourceType, "resource-type", "machine", "What kind of entity produces the log (e.g. 'master')")
	f.StringVar(&opts.resourceID, "resource-id", "", "Identifier of the entity producing the log")
	f.StringVar(&opts.logID, "log-id", "default", "ID of the log")

	opts.tsmonFlags = tsmon.NewFlags()
	opts.tsmonFlags.Target.TargetType = "task"
	opts.tsmonFlags.Target.TaskServiceName = "cloudtail"
	if defaultAutoFlush {
		opts.tsmonFlags.Flush = "auto"
	}
	opts.tsmonFlags.Register(f)
}

// processFlags validates flags, creates and configures logger, client, etc.
func (opts *commonOptions) processFlags() (state, error) {
	// Logger.
	logLevels := map[logging.Level]gol.Level{
		logging.Debug:   gol.DEBUG,
		logging.Info:    gol.INFO,
		logging.Warning: gol.WARNING,
		logging.Error:   gol.ERROR,
	}
	ctx := context.Background()
	ctx = logging.Set(ctx, gologger.New(os.Stderr, logLevels[opts.localLogLevel]))

	// Auth options.
	authOpts, err := opts.authFlags.Options()
	if err != nil {
		return state{}, err
	}
	authOpts.Context = ctx
	if opts.projectID == "" {
		if authOpts.ServiceAccountJSONPath != "" {
			opts.projectID = projectIDFromServiceAccountJSON(authOpts.ServiceAccountJSONPath)
		}
		if opts.projectID == "" {
			return state{}, fmt.Errorf("-project-id is required")
		}
	}

	// Tsmon options.
	if opts.tsmonFlags.Target.TaskJobName == "" {
		opts.tsmonFlags.Target.TaskJobName = fmt.Sprintf(
			"%s-%s-%s", opts.logID, opts.resourceType, opts.resourceID)
	}
	if err := tsmon.InitializeFromFlags(ctx, &opts.tsmonFlags); err != nil {
		return state{}, err
	}

	// Client.
	httpClient, err := auth.NewAuthenticator(auth.SilentLogin, authOpts).Client()
	if err != nil {
		return state{}, err
	}
	client, err := cloudtail.NewClient(cloudtail.ClientOptions{
		Client:       httpClient,
		Logger:       logging.Get(ctx),
		ProjectID:    opts.projectID,
		ResourceType: opts.resourceType,
		ResourceID:   opts.resourceID,
		LogID:        opts.logID,
		Debug:        opts.debug,
	})
	if err != nil {
		return state{}, err
	}

	// Buffer.
	buffer := cloudtail.NewPushBuffer(cloudtail.PushBufferOptions{
		Client: client,
		Logger: logging.Get(ctx),
	})

	return state{ctx, client, buffer}, nil
}

// defaultServiceAccountJSON returns path to a default service account
// credentials file if it exists.
func defaultServiceAccountJSONPath() string {
	path := ""
	if runtime.GOOS == "windows" {
		path = defaultServiceAccountWin
	} else {
		path = defaultServiceAccountPosix
	}
	// Ensure its readable by opening it.
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	f.Close()
	return path
}

// projectIDFromServiceAccountJSON extracts Cloud Project ID from the email
// part of the service account JSON. Returns empty string if can't do it.
func projectIDFromServiceAccountJSON(path string) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()
	var sa struct {
		ClientEmail string `json:"client_email"`
	}
	if err := json.NewDecoder(f).Decode(&sa); err != nil {
		return ""
	}
	// Expected form: <projectid>-stuff@developer.gserviceaccount.com.
	chunks := strings.Split(sa.ClientEmail, "@")
	if len(chunks) != 2 || chunks[1] != "developer.gserviceaccount.com" {
		return ""
	}
	chunks = strings.Split(chunks[0], "-")
	if len(chunks) != 2 {
		return ""
	}
	return chunks[0]
}

func catchCtrlC(handler func() error) {
	ctrlC := make(chan os.Signal, 1)
	signal.Notify(ctrlC, os.Interrupt)
	go func() {
		stopCalled := false
		for range ctrlC {
			if !stopCalled {
				stopCalled = true
				fmt.Fprintln(os.Stderr, "\nCaught Ctrl+C, flushing and exiting... Send another Ctrl+C to kill.")
				if err := handler(); err != nil {
					fmt.Fprintln(os.Stderr, "\n", err)
				}
			} else {
				os.Exit(2)
			}
		}
	}()
}

////////////////////////////////////////////////////////////////////////////////
// 'send' subcommand: sends a single line passed as CLI argument.

var cmdSend = &subcommands.Command{
	UsageLine: "send [options] -severity SEVERITY -text TEXT",
	ShortDesc: "sends a single entry to a cloud log",
	LongDesc:  "Sends a single entry to a cloud log.",
	CommandRun: func() subcommands.CommandRun {
		c := &sendRun{}
		c.commonOptions.registerFlags(&c.Flags, false)
		c.Flags.Var(&c.severity, "severity", "Log entry severity")
		c.Flags.StringVar(&c.text, "text", "", "Log entry to send")
		return c
	},
}

type sendRun struct {
	subcommands.CommandRunBase
	commonOptions

	severity cloudtail.Severity
	text     string
}

func (c *sendRun) Run(a subcommands.Application, args []string) int {
	if len(args) != 0 {
		fmt.Fprintln(os.Stderr, "This tool doesn't accept positional command line arguments")
		return 1
	}
	if c.text == "" {
		fmt.Fprintln(os.Stderr, "-text is required")
		return 1
	}

	state, err := c.commonOptions.processFlags()
	if err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		return 1
	}
	defer tsmon.Shutdown(state.context)

	state.buffer.Add([]cloudtail.Entry{
		{
			Timestamp:   time.Now(),
			Severity:    c.severity,
			TextPayload: c.text,
		},
	})
	abort := make(chan struct{}, 1)
	catchCtrlC(func() error {
		abort <- struct{}{}
		return nil
	})
	if err := state.buffer.Stop(abort); err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		return 1
	}
	return 0
}

////////////////////////////////////////////////////////////////////////////////
// 'pipe' subcommand: reads stdin and sends each line as a separate log entry.

var cmdPipe = &subcommands.Command{
	UsageLine: "pipe [options]",
	ShortDesc: "sends each line of stdin as a separate log entry",
	LongDesc:  "Sends each line of stdin as a separate log entry",
	CommandRun: func() subcommands.CommandRun {
		c := &pipeRun{}
		c.commonOptions.registerFlags(&c.Flags, true)
		return c
	},
}

type pipeRun struct {
	subcommands.CommandRunBase
	commonOptions
}

func (c *pipeRun) Run(a subcommands.Application, args []string) int {
	if len(args) != 0 {
		fmt.Fprintln(os.Stderr, "This tool doesn't accept positional command line arguments")
		return 1
	}

	state, err := c.commonOptions.processFlags()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	defer tsmon.Shutdown(state.context)

	err1 := cloudtail.PipeFromReader(
		os.Stdin, cloudtail.StdParser(), state.buffer, logging.Get(state.context))
	if err1 != nil {
		fmt.Fprintln(os.Stderr, err1)
	}
	abort := make(chan struct{}, 1)
	catchCtrlC(func() error {
		abort <- struct{}{}
		return nil
	})
	err2 := state.buffer.Stop(abort)
	if err2 != nil {
		fmt.Fprintln(os.Stderr, err2)
	}
	if err1 != nil || err2 != nil {
		return 1
	}
	return 0
}

////////////////////////////////////////////////////////////////////////////////
// 'tail' subcommand: tails a file and sends each line as a log entry.

var cmdTail = &subcommands.Command{
	UsageLine: "tail [options] -path PATH",
	ShortDesc: "tails a file and sends each line as a log entry",
	LongDesc:  "Tails a file and sends each line as a log entry. Stops by SIGINT.",
	CommandRun: func() subcommands.CommandRun {
		c := &tailRun{}
		c.commonOptions.registerFlags(&c.Flags, true)
		c.Flags.StringVar(&c.path, "path", "", "Path to a file to tail")
		return c
	},
}

type tailRun struct {
	subcommands.CommandRunBase
	commonOptions

	path string
}

func (c *tailRun) Run(a subcommands.Application, args []string) int {
	if len(args) != 0 {
		fmt.Fprintln(os.Stderr, "This tool doesn't accept positional command line arguments")
		return 1
	}
	if c.path == "" {
		fmt.Fprintln(os.Stderr, "-path is required")
		return 1
	}

	state, err := c.commonOptions.processFlags()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	defer tsmon.Shutdown(state.context)

	tailer, err := cloudtail.NewTailer(cloudtail.TailerOptions{
		Path:       c.path,
		Parser:     cloudtail.StdParser(),
		PushBuffer: state.buffer,
		Logger:     logging.Get(state.context),
		SeekToEnd:  true,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	catchCtrlC(tailer.Stop)

	fail := false
	if err1 := tailer.Wait(); err1 != nil {
		fmt.Fprintln(os.Stderr, err1)
		fail = true
	}
	if err2 := state.buffer.Stop(nil); err2 != nil {
		fmt.Fprintln(os.Stderr, err2)
		fail = true
	}
	if fail {
		return 1
	}
	return 0
}

////////////////////////////////////////////////////////////////////////////////

var application = &subcommands.DefaultApplication{
	Name:  "cloudtail",
	Title: "Tail logs and send them to Cloud Logging",
	Commands: []*subcommands.Command{
		subcommands.CmdHelp,
		cipd.SubcommandVersion,

		// Main commands.
		cmdSend,
		cmdPipe,
		cmdTail,

		// Authentication related commands.
		authcli.SubcommandInfo(authOptions, "whoami"),
		authcli.SubcommandLogin(authOptions, "login"),
		authcli.SubcommandLogout(authOptions, "logout"),
	},
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
