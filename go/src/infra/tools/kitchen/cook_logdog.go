// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"io"
	"os"
	"path/filepath"
	"time"

	"golang.org/x/net/context"

	"infra/libs/infraenv"

	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/proto/milo"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/common/system/exitcode"
	grpcLogging "github.com/luci/luci-go/grpc/logging"
	"github.com/luci/luci-go/logdog/client/annotee"
	"github.com/luci/luci-go/logdog/client/annotee/annotation"
	"github.com/luci/luci-go/logdog/client/butler"
	"github.com/luci/luci-go/logdog/client/butler/bootstrap"
	"github.com/luci/luci-go/logdog/client/butler/output"
	fileOut "github.com/luci/luci-go/logdog/client/butler/output/file"
	out "github.com/luci/luci-go/logdog/client/butler/output/logdog"
	"github.com/luci/luci-go/logdog/client/butler/streamserver"
	"github.com/luci/luci-go/logdog/client/butler/streamserver/localclient"
)

const (
	// defaultRPCTimeout is the default LogDog RPC timeout to apply.
	defaultRPCTimeout = 30 * time.Second

	// logDogViewerURLTag is a special LogDog tag that is recognized by the LogDog
	// viewer as a link to the log stream's build page.
	logDogViewerURLTag = "logdog.viewer_url"
)

// disableGRPCLogging routes gRPC log messages that are emitted through our
// logger. We only log gRPC prints if our logger is configured to log
// debug-level or lower, which it isn't by default.
func disableGRPCLogging(ctx context.Context) {
	grpcLogging.Install(log.Get(ctx), log.IsLogging(ctx, log.Debug))
}

// runWithLogdogButler runs the supplied command through the a LogDog Butler
// engine instance. This involves:
//	- Configuring / setting up the Butler.
//	- Initiating a LogDog Pub/Sub Output, registering with remote server.
//	- Running the recipe process.
//	  - Optionally, hook its output streams up through an Annotee processor.
//	  - Otherwise, wait for the process to finish.
//	- Shut down the Butler instance.
// If recipe engine returns non-zero value, the returned err is nil.
func (c *cookRun) runWithLogdogButler(ctx context.Context, rr *recipeRun, env environ.Env) (rc int, build *milo.Step, err error) {
	flags := c.CookFlags.LogDogFlags

	log.Infof(ctx, "Using LogDog URL: %s", flags.AnnotationURL)

	// Install a global gRPC logger adapter. This routes gRPC log messages that
	// are emitted through our logger. We only log gRPC prints if our logger is
	// configured to log debug-level or lower.
	disableGRPCLogging(ctx)

	// We need to dump initial properties so our annotation stream includes them.
	rr.opArgs.AnnotationFlags.EmitInitialProperties = true

	// Construct our global tags. We will prefer user-supplied tags to our
	// generated ones.
	globalTags := make(map[string]string, len(flags.GlobalTags)+1)
	if c.BuildURL != "" {
		globalTags[logDogViewerURLTag] = c.BuildURL
	}
	if err := c.mode.addLogDogGlobalTags(globalTags, rr.properties, env); err != nil {
		return 0, nil, errors.Annotate(err).Reason("failed to add global tags").Err()
	}
	for k, v := range flags.GlobalTags {
		globalTags[k] = v
	}

	// Create our stream server instance.
	streamServer, err := c.getLogDogStreamServer(withNonCancel(ctx))
	if err != nil {
		return 0, nil, errors.Annotate(err).Reason("failed to generate stream server").Err()
	}

	if err := streamServer.Listen(); err != nil {
		return 0, nil, errors.Annotate(err).Reason("failed to listen on stream server").Err()
	}
	defer func() {
		if streamServer != nil {
			streamServer.Close()
		}
	}()

	log.Debugf(ctx, "Generated stream server at: %s", streamServer.Address())

	// Use the annotation stream's prefix component for our Butler run.
	prefix, annoName := flags.AnnotationURL.Path.Split()
	// Determine our base path and annotation subpath.
	basePath, annoSubpath := annoName.Split()

	// Augment our environment with Butler parameters.
	bsEnv := bootstrap.Environment{
		Project:         flags.AnnotationURL.Project,
		Prefix:          prefix,
		StreamServerURI: streamServer.Address(),
		CoordinatorHost: flags.AnnotationURL.Host,
	}
	bsEnv.Augment(env)

	// Start our bootstrapped subprocess.
	//
	// We need to consume all of its streams prior to waiting for completion (see
	// exec.Cmd).
	//
	// We'll set up our own cancellation function to help ensure that the process
	// is properly terminated regardless of any encountered errors.
	procCtx, procCancelFunc := context.WithCancel(ctx)
	defer procCancelFunc()

	proc, err := rr.command(procCtx, filepath.Join(c.TempDir, "rr"), env)
	if err != nil {
		return 0, nil, errors.Annotate(err).Reason("failed to build recipe comamnd").Err()
	}

	// Register and instantiate our LogDog Output.
	var o output.Output
	if flags.FilePath == "" {
		// Set up authentication.
		authOpts := infraenv.DefaultAuthOptions()
		authOpts.Scopes = out.Scopes()
		switch {
		case flags.ServiceAccountJSONPath != "":
			authOpts.ServiceAccountJSONPath = flags.ServiceAccountJSONPath
			authOpts.Method = auth.ServiceAccountMethod

		case infraenv.OnGCE():
			authOpts.Method = auth.GCEMetadataMethod
			break

		default:
			// No service account specified, so load the LogDog credentials from the
			// local bot deployment.
			credPath, err := infraenv.GetLogDogServiceAccountJSON()
			if err != nil {
				return 0, nil, errors.Annotate(err).Reason("failed to get LogDog service account JSON path").Err()
			}
			authOpts.ServiceAccountJSONPath = credPath
			authOpts.Method = auth.ServiceAccountMethod
		}
		authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)

		ocfg := out.Config{
			Auth:    authenticator,
			Host:    flags.AnnotationURL.Host,
			Project: flags.AnnotationURL.Project,
			Prefix:  prefix,
			SourceInfo: []string{
				"Kitchen",
			},
			RPCTimeout:     defaultRPCTimeout,
			PublishContext: withNonCancel(ctx),
		}

		var err error
		if o, err = ocfg.Register(ctx); err != nil {
			return 0, nil, errors.Annotate(err).Reason("failed to create LogDog Output instance").Err()
		}
	} else {
		// Debug: Use a file output.
		ocfg := fileOut.Options{
			Path: flags.FilePath,
		}
		o = ocfg.New(ctx)
	}
	defer o.Close()

	butlerCfg := butler.Config{
		Output:       o,
		Project:      flags.AnnotationURL.Project,
		Prefix:       prefix,
		BufferLogs:   true,
		MaxBufferAge: butler.DefaultMaxBufferAge,
		GlobalTags:   globalTags,
	}
	if flags.LogDogOnly && (flags.LogDogSendIOKeepAlives || c.mode.needsIOKeepAlive()) {
		// If we're not teeing, we need to issue keepalives so our executor doesn't
		// kill us due to lack of I/O.
		butlerCfg.IOKeepAliveInterval = 5 * time.Minute
		butlerCfg.IOKeepAliveWriter = os.Stderr
	}

	ncCtx := withNonCancel(ctx)
	b, err := butler.New(ncCtx, butlerCfg)
	if err != nil {
		return 0, nil, errors.Annotate(err).Reason("failed to create Butler instance").Err()
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

	b.AddStreamServer(streamServer)
	streamServer = nil

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
	printCommand(ctx, proc)

	if err = proc.Start(); err != nil {
		err = errors.Annotate(err).Reason("failed to start command").Err()
		return
	}
	defer func() {
		// If we've encountered an error, cancel our process.
		if err != nil {
			procCancelFunc()
		}

		// Run our command and collect its return code.
		ierr := proc.Wait()
		if waitRC, has := exitcode.Get(ierr); has {
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

	annoteeOpts := annotee.Options{
		Base:                   basePath,
		AnnotationSubpath:      annoSubpath,
		Client:                 localclient.New(b),
		Execution:              annotation.ProbeExecution(proc.Args, proc.Env, proc.Dir),
		TeeText:                !flags.LogDogOnly,
		TeeAnnotations:         !flags.LogDogOnly || c.mode.alwaysForwardAnnotations(),
		MetadataUpdateInterval: 30 * time.Second,
		Offline:                false,
		CloseSteps:             true,
	}
	if c.mode.shouldEmitLogDogLinks() {
		annoteeOpts.LinkGenerator = &annotee.CoordinatorLinkGenerator{
			Host:    flags.AnnotationURL.Host,
			Project: flags.AnnotationURL.Project,
			Prefix:  prefix,
		}
	}
	annoteeProcessor := annotee.New(ncCtx, annoteeOpts)
	defer func() {
		as := annoteeProcessor.Finish()
		build = as.RootStep().Proto()
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
			StripAnnotations: !flags.LogDogOnly,
		},
		{
			Reader:           stderr,
			Name:             annotee.STDERR,
			Annotate:         true,
			StripAnnotations: !flags.LogDogOnly,
		},
	}
	if annoteeOpts.TeeText || annoteeOpts.TeeAnnotations {
		streams[0].Tee = os.Stdout
		streams[1].Tee = os.Stderr
	}

	// Run the process' output streams through Annotee. This will block until
	// they are all consumed.
	if err = annoteeProcessor.RunStreams(streams); err != nil {
		err = errors.Annotate(err).Reason("failed to process streams through Annotee").Err()
		return
	}

	// Our process and Butler instance will be consumed in our teardown
	// defer() statements.
	return
}

// getLogDogStreamServer returns a LogDog stream server instance configured for
// the current operating system.
//
// Because Windows doesn't have UNIX domain sockets, and Linux doesn't have
// named pipes, this becomes platform-specific.
func (c *cookRun) getLogDogStreamServer(ctx context.Context) (streamserver.StreamServer, error) {
	return getLogDogStreamServerForPlatform(ctx, c.TempDir)
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
