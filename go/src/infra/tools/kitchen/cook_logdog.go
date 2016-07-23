// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"flag"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/exec"
	"sync"
	"time"

	"infra/libs/infraenv"

	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/config"
	"github.com/luci/luci-go/common/ctxcmd"
	"github.com/luci/luci-go/common/environ"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/logdog/client/annotee"
	"github.com/luci/luci-go/logdog/client/annotee/annotation"
	"github.com/luci/luci-go/logdog/client/butler"
	"github.com/luci/luci-go/logdog/client/butler/bootstrap"
	"github.com/luci/luci-go/logdog/client/butler/output"
	fileOut "github.com/luci/luci-go/logdog/client/butler/output/file"
	out "github.com/luci/luci-go/logdog/client/butler/output/logdog"
	"github.com/luci/luci-go/logdog/client/butlerlib/streamclient"
	"github.com/luci/luci-go/logdog/client/butlerlib/streamproto"
	"github.com/luci/luci-go/logdog/common/types"

	"github.com/golang/protobuf/proto"
	"golang.org/x/net/context"
)

type cookLogDogParams struct {
	host    string
	project string
	prefix  types.StreamName
	annotee bool
	tee     bool

	filePath               string
	serviceAccountJSONPath string
}

func (p *cookLogDogParams) addFlags(fs *flag.FlagSet) {
	fs.StringVar(
		&p.host,
		"logdog-host",
		"",
		"The name of the LogDog host.")
	fs.StringVar(
		&p.project,
		"logdog-project",
		"",
		"The name of the LogDog project to log into. Projects have different ACL sets, "+
			"so choose this appropriately.")
	fs.Var(
		&p.prefix,
		"logdog-prefix",
		"The LogDog stream Prefix to use. If empty, one will be constructed from the Swarming "+
			"task parameters (found in enviornment).")
	fs.BoolVar(
		&p.annotee,
		"logdog-enable-annotee",
		true,
		"Process bootstrap STDOUT/STDERR annotations through Annotee.")
	fs.BoolVar(
		&p.tee,
		"logdog-tee",
		true,
		"Tee bootstrapped STDOUT and STDERR through Kitchen. If false, these will only be sent as LogDog streams")
	fs.StringVar(
		&p.filePath,
		"logdog-debug-out-file",
		"",
		"If specified, write all generated logs to this path instead of sending them.")
	fs.StringVar(
		&p.serviceAccountJSONPath,
		"logdog-service-account-json-path",
		"",
		"If specified, use the service account JSON file at this path. Otherwise, autodetect.")
}

func (p *cookLogDogParams) active() bool {
	return p.host != "" || p.project != "" || p.prefix != ""
}

// emitAnnotations returns true if the cook command should emit additional
// annotations.
//
// If we're streaming solely to LogDog, it makes no sense to emit extra
// annotations, since nothing will consume them; however, if we're tee-ing, we
// will continue to emit additional annotations in case something is looking
// at the tee'd output.
//
// Note that this could create an incongruity between the LogDog-emitted
// annotations and the annotations in the STDOUT stream.
func (p *cookLogDogParams) emitAnnotations() bool {
	return p.tee || !p.active()
}

func (p *cookLogDogParams) validate() error {
	if p.project == "" {
		return fmt.Errorf("a LogDog project must be supplied (-logdog-project)")
	}
	return nil
}

func (p *cookLogDogParams) getPrefix(env environ.Env) (types.StreamName, error) {
	if p.prefix != "" {
		return p.prefix, nil
	}

	// Construct our LogDog prefix from the Swarming task parameters. The server
	// will be exported as a URL. We want the "host" parameter from this URL.
	server, _ := env.Get("SWARMING_SERVER")
	serverURL, err := url.Parse(server)
	if err != nil {
		return "", errors.Annotate(err).Reason("failed to parse SWARMING_SERVER URL %(value)q").
			D("value", server).Err()
	}

	host := serverURL.Host
	if serverURL.Scheme == "" {
		// SWARMING_SERVER is not a full URL, so use its Path instead of its Host.
		host = serverURL.Path
	}
	if host == "" {
		return "", errors.Reason("missing or empty SWARMING_SERVER host in %(value)q").
			D("value", server).Err()
	}

	taskID, _ := env.Get("SWARMING_TASK_ID")
	if taskID == "" {
		return "", errors.Reason("missing or empty SWARMING_TASK_ID").Err()
	}

	return types.MakeStreamName("", "swarm", host, taskID)
}

// runWithLogdogButler rus the supplied command through the a LogDog Butler
// engine instance. This involves:
//	- Determine a LogDog Prefix.
//	- Configuring / setting up the Butler.
//	- Initiating a LogDog Pub/Sub Output, registering with remote server.
//	- Running the recipe process.
//	  - Optionally, hook its output streams up through an Annotee processor.
//	  - Otherwise, wait for the process to finish.
//	- Shut down the Butler instance.
func (c *cookRun) runWithLogdogButler(ctx context.Context, cmd *exec.Cmd) (rc int, err error) {
	// Get our task's environment.
	var env environ.Env
	if cmd.Env != nil {
		env = environ.New(cmd.Env)
	} else {
		env = environ.System()
	}

	prefix, err := c.logdog.getPrefix(env)
	if err != nil {
		return 0, errors.Annotate(err).Reason("failed to get LogDog prefix").Err()
	}
	log.Fields{
		"prefix": prefix,
	}.Infof(ctx, "Using LogDog prefix: %q", prefix)

	// Set up authentication.
	authOpts := auth.Options{
		Scopes: out.Scopes(),
	}
	switch {
	case c.logdog.serviceAccountJSONPath != "":
		authOpts.ServiceAccountJSONPath = c.logdog.serviceAccountJSONPath

	case infraenv.OnGCE():
		// Do nothing, auth will automatically use GCE metadata.
		break

	default:
		// No service account specified, so load the LogDog credentials from the
		// local bot deployment.
		credPath, err := infraenv.GetLogDogServiceAccountJSON()
		if err != nil {
			return 0, errors.Annotate(err).Reason("failed to get LogDog service account JSON path").Err()
		}
		authOpts.ServiceAccountJSONPath = credPath
	}
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)

	// Register and instantiate our LogDog Output.
	var o output.Output
	if c.logdog.filePath == "" {
		ocfg := out.Config{
			Auth:    authenticator,
			Host:    c.logdog.host,
			Project: config.ProjectName(c.logdog.project),
			Prefix:  prefix,
			SourceInfo: []string{
				"Kitchen",
			},
			PublishContext: withNonCancel(ctx),
		}

		var err error
		if o, err = ocfg.Register(ctx); err != nil {
			return 0, errors.Annotate(err).Reason("failed to create LogDog Output instance").Err()
		}
	} else {
		// Debug: Use a file output.
		ocfg := fileOut.Options{
			Path: c.logdog.filePath,
		}
		o = ocfg.New(ctx)
	}
	defer o.Close()

	butlerCfg := butler.Config{
		Output:       o,
		Project:      config.ProjectName(c.logdog.project),
		Prefix:       prefix,
		BufferLogs:   true,
		MaxBufferAge: butler.DefaultMaxBufferAge,
	}

	// If we're teeing and we're not using Annotee, tee our subprocess' STDOUT
	// and STDERR through Kitchen's STDOUT/STDERR.
	//
	// If we're using Annotee, we will configure this in the Annotee setup
	// directly.
	if c.logdog.tee && !c.logdog.annotee {
		butlerCfg.TeeStdout = os.Stdout
		butlerCfg.TeeStderr = os.Stderr
	}

	ncCtx := withNonCancel(ctx)
	b, err := butler.New(ncCtx, butlerCfg)
	if err != nil {
		err = errors.Annotate(err).Reason("failed to create Butler instance").Err()
		return
	}
	defer func() {
		b.Activate()
		if ierr := b.Wait(); ierr != nil {
			ierr = errors.Annotate(ierr).Reason("failed to Wait() for Butler").Err()
			logAnnotatedErr(ctx, ierr)

			// Promote to function output error if we don't have one yet.
			if err == nil {
				err = ierr
			}
		}
	}()

	// Wrap our incoming command in a CtxCmd.
	proc := ctxcmd.CtxCmd{
		Cmd: cmd,
	}

	// Augment our environment with Butler parameters.
	bsEnv := bootstrap.Environment{
		Project: config.ProjectName(c.logdog.project),
		Prefix:  c.logdog.prefix,
	}
	bsEnv.Augment(env)
	proc.Env = env.Sorted()

	// Build pipes for our STDOUT and STDERR streams.
	stdout, err := proc.StdoutPipe()
	if err != nil {
		err = errors.Annotate(err).Reason("failed to get STDOUT pipe").Err()
		return
	}
	defer stdout.Close()

	stderr, err := proc.StderrPipe()
	if err != nil {
		err = errors.Annotate(err).Reason("failed to get STDERR pipe").Err()
		return
	}
	defer stderr.Close()

	// Start our bootstrapped subprocess.
	//
	// We need to consume all of its streams prior to waiting for completion (see
	// exec.Cmd).
	//
	// We'll set up our own cancellation function to help ensure that the process
	// is properly terminated regardless of any encountered errors.
	ctx, cancelFunc := context.WithCancel(ctx)
	if err = proc.Start(ctx); err != nil {
		err = errors.Annotate(err).Reason("failed to start command").Err()
		return
	}
	defer func() {
		// If we've encountered an error, cancel our process.
		if err != nil {
			cancelFunc()
		}

		// Run our command and collect its return code.
		ierr := proc.Wait()
		if waitRC, has := ctxcmd.ExitCode(ierr); has {
			rc = waitRC
		} else {
			ierr = errors.Annotate(ierr).Reason("failed to Wait() for process").Err()
			logAnnotatedErr(ctx, ierr)

			// Promote to function output error if we don't have one yet.
			if err == nil {
				err = ierr
			}
		}
	}()

	if c.logdog.annotee {
		annoteeProcessor := annotee.New(ncCtx, annotee.Options{
			Base:                   "recipes",
			Client:                 streamclient.NewLocal(b),
			Execution:              annotation.ProbeExecution(proc.Args, proc.Env, proc.Dir),
			MetadataUpdateInterval: 30 * time.Second,
			Offline:                false,
			CloseSteps:             true,
		})
		defer func() {
			as := annoteeProcessor.Finish()
			log.Infof(ctx, "Annotations finished:\n%s", proto.MarshalTextString(as.RootStep().Proto()))
		}()

		// Run STDOUT/STDERR streams through the processor. This will block until
		// both streams are closed.
		//
		// If we're teeing, we will tee the full stream, including annotations.
		streams := []*annotee.Stream{
			{
				Reader:           stdout,
				Name:             annotee.STDOUT,
				Annotate:         true,
				StripAnnotations: !c.logdog.tee,
			},
			{
				Reader:           stderr,
				Name:             annotee.STDERR,
				Annotate:         true,
				StripAnnotations: !c.logdog.tee,
			},
		}
		if c.logdog.tee {
			streams[0].Tee = os.Stdout
			streams[1].Tee = os.Stderr
		}

		// Run the process' output streams through Annotee. This will block until
		// they are all consumed.
		if err = annoteeProcessor.RunStreams(streams); err != nil {
			err = errors.Annotate(err).Reason("failed to process streams through Annotee").Err()
			return
		}
	} else {
		// Get our STDOUT / STDERR stream flags. Tailor them to match Annotee.
		stdoutFlags := annotee.TextStreamFlags(ctx, annotee.STDOUT)
		stderrFlags := annotee.TextStreamFlags(ctx, annotee.STDERR)
		if c.logdog.tee {
			stdoutFlags.Tee = streamproto.TeeStdout
			stderrFlags.Tee = streamproto.TeeStderr
		}

		// Wait for our STDOUT / STDERR streams to complete.
		var wg sync.WaitGroup
		stdout = &callbackReadCloser{stdout, wg.Done}
		stderr = &callbackReadCloser{stderr, wg.Done}
		wg.Add(2)

		// Explicitly add these streams to the Butler.
		if err = b.AddStream(stdout, *stdoutFlags.Properties()); err != nil {
			err = errors.Annotate(err).Reason("failed to add STDOUT stream to Butler").Err()
			return
		}
		if err = b.AddStream(stderr, *stderrFlags.Properties()); err != nil {
			err = errors.Annotate(err).Reason("failed to add STDERR stream to Butler").Err()
			return
		}

		// Wait for the streams to be consumed.
		wg.Wait()
	}

	// Our process and Butler instance will be consumed in our teardown
	// defer() statements.
	return
}

// nonCancelContext is a context.Context which deliberately ignores cancellation
// installed in its parent Contexts. This is used to shield the LogDog output
// from having its operations cancelled if the supplied Context is cancelled,
// allowing it to flush.
type nonCancelContext struct {
	base  context.Context
	doneC chan struct{}
}

func withNonCancel(ctx context.Context) context.Context {
	return &nonCancelContext{
		base:  ctx,
		doneC: make(chan struct{}),
	}
}

func (c *nonCancelContext) Deadline() (time.Time, bool)       { return time.Time{}, false }
func (c *nonCancelContext) Done() <-chan struct{}             { return c.doneC }
func (c *nonCancelContext) Err() error                        { return nil }
func (c *nonCancelContext) Value(key interface{}) interface{} { return c.base.Value(key) }

// callbackReadCloser invokes a callback method when closed.
type callbackReadCloser struct {
	io.ReadCloser
	callback func()
}

func (c *callbackReadCloser) Close() error {
	defer c.callback()
	return c.ReadCloser.Close()
}
