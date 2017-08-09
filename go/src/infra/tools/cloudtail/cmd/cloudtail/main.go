// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"runtime"
	"strings"
	"time"

	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"go.chromium.org/luci/cipd/version"
	"go.chromium.org/luci/client/authcli"
	"go.chromium.org/luci/common/auth"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/common/tsmon"

	"infra/libs/infraenv"
	"infra/tools/cloudtail"
)

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
	flushTimeout  time.Duration
	bufferingTime time.Duration
	debug         bool

	projectID    string
	resourceType string
	resourceID   string
	logID        string
}

type state struct {
	id     cloudtail.ClientID
	client cloudtail.Client
	buffer cloudtail.PushBuffer
}

// registerFlags adds all CLI flags to the flag set.
func (opts *commonOptions) registerFlags(f *flag.FlagSet, defaultAuthOpts auth.Options, defaultAutoFlush bool) {
	// Default log level.
	opts.localLogLevel = logging.Warning

	opts.authFlags.Register(f, defaultAuthOpts)
	f.Var(&opts.localLogLevel, "local-log-level",
		"The logging level of local logger (for cloudtail own logs): debug, info, warning, error")
	f.DurationVar(&opts.flushTimeout, "flush-timeout", 5*time.Second,
		"How long to wait for all pending data to be flushed when exiting")
	f.DurationVar(&opts.bufferingTime, "buffering-time", cloudtail.DefaultFlushTimeout,
		"How long to buffer a log line before flushing it (larger values improve batching at the cost of latency)")
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
func (opts *commonOptions) processFlags(ctx context.Context) (context.Context, state, error) {
	// Logger.
	ctx = logging.SetLevel(ctx, opts.localLogLevel)

	// Auth options.
	authOpts, err := opts.authFlags.Options()
	if err != nil {
		return ctx, state{}, err
	}
	if opts.projectID == "" {
		if authOpts.ServiceAccountJSONPath != "" {
			opts.projectID = projectIDFromServiceAccountJSON(authOpts.ServiceAccountJSONPath)
			if opts.projectID != "" {
				logging.Debugf(ctx, "Guessed project ID from the service account JSON: %s", opts.projectID)
			}
		}
		if opts.projectID == "" {
			return ctx, state{}, fmt.Errorf("-project-id is required")
		}
	}

	// Tsmon options.
	if opts.tsmonFlags.Target.TaskJobName == "" {
		opts.tsmonFlags.Target.TaskJobName = fmt.Sprintf(
			"%s-%s-%s", opts.logID, opts.resourceType, opts.resourceID)
	}
	if err := tsmon.InitializeFromFlags(ctx, &opts.tsmonFlags); err != nil {
		return ctx, state{}, err
	}

	// Client.
	httpClient, err := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts).Client()
	if err != nil {
		return ctx, state{}, err
	}
	id := cloudtail.ClientID{
		ResourceType: opts.resourceType,
		ResourceID:   opts.resourceID,
		LogID:        opts.logID,
	}
	client, err := cloudtail.NewClient(cloudtail.ClientOptions{
		ClientID:  id,
		Client:    httpClient,
		ProjectID: opts.projectID,
		Debug:     opts.debug,
	})
	if err != nil {
		return ctx, state{}, err
	}

	// Buffer.
	buffer := cloudtail.NewPushBuffer(cloudtail.PushBufferOptions{
		Client:       client,
		FlushTimeout: opts.bufferingTime,
	})

	return ctx, state{id, client, buffer}, nil
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

// projectIDFromServiceAccountJSON extracts Cloud Project ID from the service
// account JSON.
//
// It tries to use 'project_id' key, if present, and falls back to email
// parsing otherwise (for old JSON files that don't have project_id field, but
// use "<projectid>-stuff@developer.gserviceaccount.com" email format).
//
// Returns empty string if can't do it.
func projectIDFromServiceAccountJSON(path string) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()
	var sa struct {
		ProjectID   string `json:"project_id"`
		ClientEmail string `json:"client_email"`
	}
	if err := json.NewDecoder(f).Decode(&sa); err != nil {
		return ""
	}
	if sa.ProjectID != "" {
		return sa.ProjectID
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

func cmdSend(defaultAuthOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "send [options] -severity SEVERITY -text TEXT",
		ShortDesc: "sends a single entry to a cloud log",
		LongDesc:  "Sends a single entry to a cloud log.",
		CommandRun: func() subcommands.CommandRun {
			c := &sendRun{}
			c.commonOptions.registerFlags(&c.Flags, defaultAuthOpts, false)
			c.Flags.Var(&c.severity, "severity", "Log entry severity")
			c.Flags.StringVar(&c.text, "text", "", "Log entry to send")
			return c
		},
	}
}

type sendRun struct {
	subcommands.CommandRunBase
	commonOptions

	severity cloudtail.Severity
	text     string
}

func (c *sendRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if len(args) != 0 {
		fmt.Fprintf(os.Stderr, "Cloudtail send doesn't accept positional command line arguments %q\n", args)
		return 1
	}
	if c.text == "" {
		fmt.Fprintln(os.Stderr, "-text is required")
		return 1
	}

	ctx, state, err := c.commonOptions.processFlags(cli.GetContext(a, c, env))
	if err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		return 1
	}
	defer tsmon.Shutdown(ctx)

	// Sending one item shouldn't involve any buffering. So make SIGINT
	// (or timeout) abort the whole pipeline right away.
	ctx, abort := context.WithCancel(ctx)
	catchCtrlC(func() error {
		abort()
		return nil
	})
	ctx, _ = clock.WithTimeout(ctx, c.flushTimeout)

	state.buffer.Start(ctx)
	state.buffer.Send(ctx, cloudtail.Entry{
		Timestamp:   time.Now(),
		Severity:    c.severity,
		TextPayload: c.text,
	})
	if err := state.buffer.Stop(ctx); err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		return 1
	}

	return 0
}

////////////////////////////////////////////////////////////////////////////////
// 'pipe' subcommand: reads stdin and sends each line as a separate log entry.

func cmdPipe(defaultAuthOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "pipe [options]",
		ShortDesc: "sends each line of stdin as a separate log entry",
		LongDesc:  "Sends each line of stdin as a separate log entry",
		CommandRun: func() subcommands.CommandRun {
			c := &pipeRun{}
			c.commonOptions.registerFlags(&c.Flags, defaultAuthOpts, true)
			c.Flags.IntVar(&c.lineBufferSize, "line-buffer-size", 100000,
				"Number of log lines to buffer in-memory.  0 disables buffering and "+
					"makes cloudtail block while flushing lines to the API.")
			return c
		},
	}
}

type pipeRun struct {
	subcommands.CommandRunBase
	commonOptions

	lineBufferSize int
}

func (c *pipeRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if len(args) != 0 {
		fmt.Fprintf(os.Stderr, "Cloudtail pipe doesn't accept positional command line arguments %q\n", args)
		return 1
	}

	ctx, state, err := c.commonOptions.processFlags(cli.GetContext(a, c, env))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	defer tsmon.Shutdown(ctx)

	// We need to wrap stdin in a io.Pipe to be able to prematurely abort reads on
	// SIGINT. There seem to be no reliable way of aborting pending os.Stdin read
	// on Linux. Closing the file descriptor doesn't work. So on SIGINT we keep
	// the blocked stdin read hanging in the goroutine, but forcefully close the
	// write end of the pipe to shutdown cloudtail.PipeReader below. Eventually
	// stdin read unblocks, finds a closed io.Pipe and aborts the goroutine.
	pipeR, pipeW := io.Pipe()
	go func() {
		defer pipeW.Close()
		io.Copy(pipeW, os.Stdin)
	}()
	catchCtrlC(pipeW.Close)

	pipeReader := cloudtail.PipeReader{
		ClientID:       state.id,
		Source:         pipeR,
		PushBuffer:     state.buffer,
		Parser:         cloudtail.StdParser(),
		LineBufferSize: c.lineBufferSize,
	}

	// On EOF (which also happens on SIGINT) start a countdown that will abort
	// the context and unblock everything even if some data wasn't sent.
	ctx, abort := context.WithCancel(ctx)
	pipeReader.OnEOF = func() {
		logging.Debugf(ctx, "EOF detected, aborting in %s", c.flushTimeout)
		go func() {
			time.Sleep(c.flushTimeout)
			abort()
		}()
	}

	state.buffer.Start(ctx)

	err1 := pipeReader.Run(ctx)
	if err1 != nil {
		fmt.Fprintln(os.Stderr, err1)
	}
	err2 := state.buffer.Stop(ctx)
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

func cmdTail(defaultAuthOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "tail [options] -path PATH",
		ShortDesc: "tails a file and sends each line as a log entry",
		LongDesc:  "Tails a file and sends each line as a log entry. Stops by SIGINT.",
		CommandRun: func() subcommands.CommandRun {
			c := &tailRun{}
			c.commonOptions.registerFlags(&c.Flags, defaultAuthOpts, true)
			c.Flags.StringVar(&c.path, "path", "", "Path to a file to tail")
			return c
		},
	}
}

type tailRun struct {
	subcommands.CommandRunBase
	commonOptions

	path string
}

func (c *tailRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if len(args) != 0 {
		fmt.Fprintf(os.Stderr, "Cloudtail tail doesn't accept positional command line arguments %q\n", args)
		return 1
	}
	if c.path == "" {
		fmt.Fprintln(os.Stderr, "-path is required")
		return 1
	}

	ctx, state, err := c.commonOptions.processFlags(cli.GetContext(a, c, env))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	defer tsmon.Shutdown(ctx)

	ctx, abort := context.WithCancel(ctx)
	state.buffer.Start(ctx)

	tailer, err := cloudtail.NewTailer(cloudtail.TailerOptions{
		Path:       c.path,
		Parser:     cloudtail.StdParser(),
		PushBuffer: state.buffer,
		SeekToEnd:  true,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}

	// Send the stop signal through tailer.Stop to properly flush everything.
	// In 'tail' mode, unlike 'pipe' mode, Ctrl+C is the only stop signal
	// (there's no EOF). At the same time start a countdown that will abort
	// the context and unblock everything even if some data wasn't sent.
	catchCtrlC(func() error {
		go func() {
			time.Sleep(c.flushTimeout)
			abort()
		}()
		tailer.Stop()
		return nil
	})
	tailer.Run(ctx) // this will block until some time after tailer.Stop is called

	// Wait until we flush everything or until the timeout. Second SIGINT
	// kills the process immediately anyhow (see catchCtrlC).
	if err := state.buffer.Stop(ctx); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}

	return 0
}

////////////////////////////////////////////////////////////////////////////////

func getApplication(defaultAuthOpts auth.Options) *cli.Application {
	return &cli.Application{
		Name:  "cloudtail",
		Title: "Tail logs and send them to Cloud Logging",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		EnvVars: map[string]subcommands.EnvVarDefinition{
			"CLOUDTAIL_DEBUG_EMULATE_429": {
				Advanced:  true,
				ShortDesc: "DEBUG/TEST: Non-empty values emulate a server response of 'Too Many Requests'.",
			},
		},

		Commands: []*subcommands.Command{
			subcommands.CmdHelp,
			version.SubcommandVersion,

			// Main commands.
			cmdSend(defaultAuthOpts),
			cmdPipe(defaultAuthOpts),
			cmdTail(defaultAuthOpts),

			// Authentication related commands.
			authcli.SubcommandInfo(defaultAuthOpts, "whoami", false),
			authcli.SubcommandLogin(defaultAuthOpts, "login", false),
			authcli.SubcommandLogout(defaultAuthOpts, "logout", false),
		},
	}
}

func main() {
	mathrand.SeedRandomly()

	authOpts := infraenv.DefaultAuthOptions()
	authOpts.ServiceAccountJSONPath = defaultServiceAccountJSONPath()
	authOpts.Scopes = []string{
		auth.OAuthScopeEmail,
		"https://www.googleapis.com/auth/logging.write",
	}

	os.Exit(subcommands.Run(getApplication(authOpts), nil))
}
