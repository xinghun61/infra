// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"flag"
	"io"
	"os"
	"path/filepath"
	"time"

	"github.com/golang/protobuf/proto"
	"golang.org/x/net/context"

	"infra/libs/infraenv"

	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
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
	"github.com/luci/luci-go/logdog/client/butlerlib/streamclient"
	"github.com/luci/luci-go/logdog/client/butlerlib/streamproto"
	"github.com/luci/luci-go/logdog/common/types"
	"github.com/luci/luci-go/swarming/tasktemplate"
)

const (
	// defaultRPCTimeout is the default LogDog RPC timeout to apply.
	defaultRPCTimeout = 30 * time.Second
)

// disableGRPCLogging routes gRPC log messages that are emitted through our
// logger. We only log gRPC prints if our logger is configured to log
// debug-level or lower, which it isn't by default.
func disableGRPCLogging(ctx context.Context) {
	grpcLogging.Install(log.Get(ctx), log.IsLogging(ctx, log.Debug))
}

type cookLogDogParams struct {
	annotationURL          string
	globalTags             streamproto.TagMap
	logDogOnly             bool
	logDogSendIOKeepAlives bool

	filePath               string
	serviceAccountJSONPath string

	// annotationAddr is the address of the LogDog annotation stream. It is
	// resolved from the "annotationURL" field during "setupAndValidate".
	annotationAddr *types.StreamAddr
}

func (p *cookLogDogParams) addFlags(fs *flag.FlagSet) {
	fs.StringVar(
		&p.annotationURL,
		"logdog-annotation-url",
		"",
		"The URL of the LogDog annotation stream to use (logdog://host/project/prefix/+/name). The LogDog "+
			"project and prefix will be extracted from this URL. This can include SwarmBucket template parameters.")
	fs.BoolVar(
		&p.logDogOnly,
		"logdog-only",
		false,
		"Send all output and annotations through LogDog. Implied by swarming mode.")
	fs.BoolVar(
		&p.logDogSendIOKeepAlives,
		"logdog-send-io-keepalives",
		false,
		"When in LogDog-only mode (-logdog-only), send I/O keepalives.")
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
	fs.Var(
		&p.globalTags,
		"logdog-tag",
		"Specify key[=value] tags to be applied to all log streams. Individual streams may override. Can "+
			"be specified multiple times.")
}

func (p *cookLogDogParams) active() bool {
	return p.annotationURL != ""
}

// shouldEmitAnnotations returns true if the cook command should emit additional
// annotations.
//
// If we're streaming solely to LogDog, it makes no sense to emit extra
// annotations, since nothing will consume them; however, if we're tee-ing, we
// will continue to emit additional annotations in case something is looking
// at the tee'd output.
//
// Note that this could create an incongruity between the LogDog-emitted
// annotations and the annotations in the STDOUT stream.
func (p *cookLogDogParams) shouldEmitAnnotations() bool {
	return !(p.logDogOnly && p.active())
}

func (p *cookLogDogParams) setupAndValidate(mode cookMode, env environ.Env) error {
	if !p.active() {
		if p.logDogOnly {
			return errors.New("LogDog flag (-logdog-only) requires annotation URL (-logdog-annotation-url)")
		}
		return nil
	}

	// Resolve templating parameters.
	var params tasktemplate.Params
	if err := mode.fillTemplateParams(env, &params); err != nil {
		return errors.Annotate(err).Reason("failed to populate template parameters").Err()
	}

	// Parse/resolve annotation URL (must be populated, since active()).
	annotationURL, err := params.Resolve(p.annotationURL)
	if err != nil {
		return errors.Annotate(err).Reason("failed to resolve LogDog annotation URL (-logdog-annotation-url)").
			D("value", p.annotationURL).
			Err()
	}
	if p.annotationAddr, err = types.ParseURL(annotationURL); err != nil {
		return errors.Annotate(err).Reason("invalid LogDog annotation URL (-logdog-annotation-url)").
			D("value", annotationURL).
			Err()
	}

	return nil
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
func (c *cookRun) runWithLogdogButler(ctx context.Context, rr *recipeRun, env environ.Env) (rc int, err error) {
	log.Infof(ctx, "Using LogDog host: %s", c.logdog.annotationAddr.URL().String())

	// Install a global gRPC logger adapter. This routes gRPC log messages that
	// are emitted through our logger. We only log gRPC prints if our logger is
	// configured to log debug-level or lower.
	disableGRPCLogging(ctx)

	// We need to dump initial properties so our annotation stream includes them.
	rr.opArgs.AnnotationFlags.EmitInitialProperties = true

	// Use the annotation stream's prefix component for our Butler run.
	prefix, annoName := c.logdog.annotationAddr.Path.Split()
	log.Infof(ctx, "Using LogDog prefix: %s", prefix)

	// Construct our global tags. We will prefer user-supplied tags to our
	// generated ones.
	globalTags := make(map[string]string, len(c.logdog.globalTags))
	if err := c.mode.addLogDogGlobalTags(globalTags, rr.properties, env); err != nil {
		return 0, errors.Annotate(err).Reason("failed to add global tags").Err()
	}
	for k, v := range c.logdog.globalTags {
		globalTags[k] = v
	}

	// Determine our base path and annotation subpath.
	basePath, annoSubpath := annoName.Split()

	// Augment our environment with Butler parameters.
	bsEnv := bootstrap.Environment{
		Project: c.logdog.annotationAddr.Project,
		Prefix:  prefix,
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
		return 0, errors.Annotate(err).Reason("failed to build recipe comamnd").Err()
	}

	// Register and instantiate our LogDog Output.
	var o output.Output
	if c.logdog.filePath == "" {
		// Set up authentication.
		authOpts := infraenv.DefaultAuthOptions()
		authOpts.Scopes = out.Scopes()
		switch {
		case c.logdog.serviceAccountJSONPath != "":
			authOpts.ServiceAccountJSONPath = c.logdog.serviceAccountJSONPath
			authOpts.Method = auth.ServiceAccountMethod

		case infraenv.OnGCE():
			authOpts.Method = auth.GCEMetadataMethod
			break

		default:
			// No service account specified, so load the LogDog credentials from the
			// local bot deployment.
			credPath, err := infraenv.GetLogDogServiceAccountJSON()
			if err != nil {
				return 0, errors.Annotate(err).Reason("failed to get LogDog service account JSON path").Err()
			}
			authOpts.ServiceAccountJSONPath = credPath
			authOpts.Method = auth.ServiceAccountMethod
		}
		authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)

		ocfg := out.Config{
			Auth:    authenticator,
			Host:    c.logdog.annotationAddr.Host,
			Project: c.logdog.annotationAddr.Project,
			Prefix:  prefix,
			SourceInfo: []string{
				"Kitchen",
			},
			RPCTimeout:     defaultRPCTimeout,
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
		Project:      c.logdog.annotationAddr.Project,
		Prefix:       prefix,
		BufferLogs:   true,
		MaxBufferAge: butler.DefaultMaxBufferAge,
		GlobalTags:   globalTags,
	}
	if c.logdog.logDogOnly && (c.logdog.logDogSendIOKeepAlives || c.mode.needsIOKeepAlive()) {
		// If we're not teeing, we need to issue keepalives so our executor doesn't
		// kill us due to lack of I/O.
		butlerCfg.IOKeepAliveInterval = 5 * time.Minute
		butlerCfg.IOKeepAliveWriter = os.Stderr
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
	printCommand(proc)

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
		Client:                 streamclient.NewLocal(b),
		Execution:              annotation.ProbeExecution(proc.Args, proc.Env, proc.Dir),
		TeeText:                !c.logdog.logDogOnly,
		TeeAnnotations:         !c.logdog.logDogOnly || c.mode.alwaysForwardAnnotations(),
		MetadataUpdateInterval: 30 * time.Second,
		Offline:                false,
		CloseSteps:             true,
	}
	if c.mode.shouldEmitLogDogLinks() {
		annoteeOpts.LinkGenerator = &annotee.CoordinatorLinkGenerator{
			Host:    c.logdog.annotationAddr.Host,
			Project: c.logdog.annotationAddr.Project,
			Prefix:  prefix,
		}
	}
	annoteeProcessor := annotee.New(ncCtx, annoteeOpts)
	defer func() {
		as := annoteeProcessor.Finish()

		// Dump the annotations on completion, unless we're already dumping them
		// to a file (debug), in which case this is redundant.
		if c.logdog.filePath == "" {
			log.Infof(ctx, "Annotations finished:\n%s", proto.MarshalTextString(as.RootStep().Proto()))
		}
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
			StripAnnotations: !c.logdog.logDogOnly,
		},
		{
			Reader:           stderr,
			Name:             annotee.STDERR,
			Annotate:         true,
			StripAnnotations: !c.logdog.logDogOnly,
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
