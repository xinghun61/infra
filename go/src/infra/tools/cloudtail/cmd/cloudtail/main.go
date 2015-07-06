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
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/maruel/subcommands"
	gol "github.com/op/go-logging"

	"infra/tools/cloudtail"
)

var logger = gologger.New(os.Stderr, gol.INFO)

var authOptions = auth.Options{
	Logger:                 logger,
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
	authFlags authcli.Flags

	projectID    string
	resourceType string
	resourceID   string
	logID        string
}

func (opts *commonOptions) registerFlags(f *flag.FlagSet) {
	opts.authFlags.Register(f, authOptions)
	f.StringVar(&opts.projectID, "project-id", "", "Cloud project ID to push logs to")
	f.StringVar(&opts.resourceType, "resource-type", "machine", "What kind of entity produces the log (e.g. 'master')")
	f.StringVar(&opts.resourceID, "resource-id", "", "Identifier of the entity producing the log")
	f.StringVar(&opts.logID, "log-id", "default", "ID of the log")
}

func (opts *commonOptions) makeClient() (cloudtail.Client, error) {
	authOpts, err := opts.authFlags.Options()
	if err != nil {
		return nil, err
	}
	if opts.projectID == "" {
		if authOpts.ServiceAccountJSONPath != "" {
			opts.projectID = projectIDFromServiceAccountJSON(authOpts.ServiceAccountJSONPath)
		}
		if opts.projectID == "" {
			return nil, fmt.Errorf("-project-id is required")
		}
	}
	client, err := auth.AuthenticatedClient(auth.SilentLogin, auth.NewAuthenticator(authOpts))
	if err != nil {
		return nil, err
	}
	return cloudtail.NewClient(cloudtail.ClientOptions{
		Client:       client,
		Logger:       logger,
		ProjectID:    opts.projectID,
		ResourceType: opts.resourceType,
		ResourceID:   opts.resourceID,
		LogID:        opts.logID,
	})
}

func (opts *commonOptions) makePushBuffer() (cloudtail.PushBuffer, error) {
	client, err := opts.makeClient()
	if err != nil {
		return nil, err
	}
	return cloudtail.NewPushBuffer(cloudtail.PushBufferOptions{
		Client: client,
		Logger: logger,
	}), nil
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

////////////////////////////////////////////////////////////////////////////////
// 'send' subcommand: sends a single line passed as CLI argument.

var cmdSend = &subcommands.Command{
	UsageLine: "send [options] -severity SEVERITY -text TEXT",
	ShortDesc: "sends a single entry to a cloud log",
	LongDesc:  "Sends a single entry to a cloud log.",
	CommandRun: func() subcommands.CommandRun {
		c := &sendRun{}
		c.commonOptions.registerFlags(&c.Flags)
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
		logger.Errorf("Unexpected command line arguments: %v", args)
		return 1
	}
	if c.text == "" {
		logger.Errorf("-text is required")
		return 1
	}
	client, err := c.commonOptions.makeClient()
	if err != nil {
		logger.Errorf("%s", err)
		return 1
	}
	err = client.PushEntries([]cloudtail.Entry{
		{
			Timestamp:   time.Now(),
			Severity:    c.severity,
			TextPayload: c.text,
		},
	})
	if err != nil {
		logger.Errorf("%s", err)
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
		c.commonOptions.registerFlags(&c.Flags)
		return c
	},
}

type pipeRun struct {
	subcommands.CommandRunBase
	commonOptions
}

func (c *pipeRun) Run(a subcommands.Application, args []string) int {
	if len(args) != 0 {
		logger.Errorf("Unexpected command line arguments: %v", args)
		return 1
	}
	buf, err := c.commonOptions.makePushBuffer()
	if err != nil {
		logger.Errorf("%s", err)
		return 1
	}
	err1 := cloudtail.PipeFromReader(os.Stdin, cloudtail.StdParser(), buf, logger)
	if err1 != nil {
		logger.Errorf("%s", err1)
	}
	err2 := buf.Stop()
	if err2 != nil {
		logger.Errorf("%s", err2)
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
		c.commonOptions.registerFlags(&c.Flags)
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
		logger.Errorf("Unexpected command line arguments: %v", args)
		return 1
	}
	if c.path == "" {
		logger.Errorf("-path is required")
		return 1
	}

	buf, err := c.commonOptions.makePushBuffer()
	if err != nil {
		logger.Errorf("%s", err)
		return 1
	}

	tailer, err := cloudtail.NewTailer(cloudtail.TailerOptions{
		Path:       c.path,
		Parser:     cloudtail.StdParser(),
		PushBuffer: buf,
		Logger:     logger,
		SeekToEnd:  true,
	})
	if err != nil {
		logger.Errorf("%s", err)
		return 1
	}
	defer cloudtail.CleanupTailer()

	ctrlC := make(chan os.Signal, 1)
	signal.Notify(ctrlC, os.Interrupt)
	go func() {
		stopCalled := false
		for _ = range ctrlC {
			if !stopCalled {
				stopCalled = true
				logger.Infof("Caught Ctrl+C, flushing and exiting... Send another Ctrl+C to kill.")
				err := tailer.Stop()
				if err != nil {
					logger.Errorf("%s", err)
				}
			} else {
				os.Exit(2)
			}
		}
	}()

	fail := false
	if err1 := tailer.Wait(); err1 != nil {
		logger.Errorf("%s", err1)
		fail = true
	}
	if err2 := buf.Stop(); err2 != nil {
		logger.Errorf("%s", err2)
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
