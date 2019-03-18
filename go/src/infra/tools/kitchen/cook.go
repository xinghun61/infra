// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"

	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	log "go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/milo"
	"go.chromium.org/luci/common/system/environ"
	"go.chromium.org/luci/common/system/exitcode"
	"go.chromium.org/luci/common/system/filesystem"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/logdog/client/annotee"
	"go.chromium.org/luci/logdog/client/annotee/annotation"
	"go.chromium.org/luci/logdog/client/butler"
	"go.chromium.org/luci/logdog/client/butler/bootstrap"
	"go.chromium.org/luci/logdog/client/butler/output"
	fileOut "go.chromium.org/luci/logdog/client/butler/output/file"
	out "go.chromium.org/luci/logdog/client/butler/output/logdog"
	"go.chromium.org/luci/logdog/client/butler/streamserver"
	"go.chromium.org/luci/logdog/client/butler/streamserver/localclient"
	"go.chromium.org/luci/logdog/common/types"
	"go.chromium.org/luci/lucictx"

	"infra/tools/kitchen/build"
	"infra/tools/kitchen/cookflags"
	"infra/tools/kitchen/third_party/recipe_engine"
)

const (
	// BootstrapStepName is the name of kitchen's step where it makes preparations
	// for running a recipe, e.g. fetches a repository.
	BootstrapStepName = "recipe bootstrap"

	// defaultRPCTimeout is the default LogDog RPC timeout to apply.
	defaultRPCTimeout = 30 * time.Second

	// logDogViewerURLTag is a special LogDog tag that is recognized by the LogDog
	// viewer as a link to the log stream's build page.
	logDogViewerURLTag = "logdog.viewer_url"
)

// cmdCook runs a recipe.
var cmdCook = &subcommands.Command{
	UsageLine: "cook -recipe <recipe>",
	ShortDesc: "bootstraps a LUCI job.",
	LongDesc:  "Bootstraps a LUCI job.",
	CommandRun: func() subcommands.CommandRun {
		var c cookRun

		c.CookFlags.Register(&c.Flags)

		return &c
	},
}

type cookRun struct {
	subcommands.CommandRunBase

	cookflags.CookFlags

	engine       recipeEngine
	kitchenProps *kitchenProperties

	systemAuth   *AuthContext // used by kitchen itself for logdog, bigquery, git
	recipeAuth   *AuthContext // used by the recipe
	buildSecrets *buildbucketpb.BuildSecrets

	bu *buildUpdater
}

// kitchenProperties defines the structure of "$kitchen" build property.
//
// It is consumed exclusively by Kitchen and not even passed along to the recipe
// engine.
type kitchenProperties struct {
	GitAuth      bool `json:"git_auth"`
	DevShell     bool `json:"devshell"`
	DockerAuth   bool `json:"docker_auth"`
	FirebaseAuth bool `json:"firebase_auth"`
}

// normalizeFlags validates and normalizes flags.
func (c *cookRun) normalizeFlags() error {
	if err := c.CookFlags.Normalize(); err != nil {
		return err
	}

	c.engine.recipeName = c.RecipeName

	return nil
}

// runRecipe runs the recipe.
func (c *cookRun) runRecipe(ctx context.Context, env environ.Env) *build.BuildRunResult {
	result := &build.BuildRunResult{
		Recipe: &build.BuildRunResult_Recipe{
			Name: c.RecipeName,
		},
	}

	fail := func(err error) *build.BuildRunResult {
		if err == nil {
			panic("do not call fail with nil err")
		}
		if result.InfraFailure != nil {
			panic("bug! forgot to return the result on previous error")
		}
		result.InfraFailure = infraFailure(err)
		return result
	}

	// The ready-to-run recipe must already be present on the file system in
	// checkout-dir.
	recipesPath, err := exec.LookPath(filepath.Join(c.CheckoutDir, "recipes"))
	if err != nil {
		return fail(errors.Annotate(err, "could not find bundled recipes").Err())
	}
	// LookPath can return an absolute OR relative path. Use Abs to make sure.
	recipesPath, err = filepath.Abs(recipesPath)
	if err != nil {
		return fail(errors.Annotate(err, "could not convert bundled recipes to abspath").Err())
	}
	c.engine.cmdPrefix = []string{recipesPath}

	// Setup our working directory. This is cwd for the recipe itself.
	// Previously this was unnecessarially configurable; Now we hard-code it to
	// "$CWD/k", which is the shortest path we can make. This is important to
	// allow tasks on Windows to have as many characters as possible; otherwise
	// they run into MAX_PATH issues.
	c.engine.workDir, err = prepareRecipeRunWorkDir("k")
	if err != nil {
		return fail(errors.Annotate(err, "failed to prepare workdir").Err())
	}

	// Tell the recipe to write the result protobuf message to a file and read
	// it below.
	c.engine.outputResultJSONFile = filepath.Join(c.TempDir, "recipe-result.json")

	// Run the recipe in the appropriate auth context by exporting it into the
	// environ of the recipe engine.
	recipeEnv := c.recipeAuth.ExportIntoEnv(env)

	result.AnnotationUrl = c.AnnotationURL.String()
	if err = c.runWithLogdogButler(ctx, recipeEnv, result); err != nil {
		return fail(errors.Annotate(err, "failed to run recipe").Err())
	}
	setAnnotationText(result.Annotations)

	// Now read the recipe result file.
	recipeResultFile, err := os.Open(c.engine.outputResultJSONFile)
	if err != nil {
		// The recipe result file must exist and be readable.
		// If it is not, it is a fatal error.
		return fail(errors.Annotate(err,
			"could not read recipe result file at %q", c.engine.outputResultJSONFile).Err())
	}
	defer recipeResultFile.Close()

	if c.RecipeResultByteLimit > 0 {
		st, err := recipeResultFile.Stat()
		if err != nil {
			return fail(errors.Annotate(err,
				"could not stat recipe result file at %q", c.engine.outputResultJSONFile).Err())
		}

		if sz := st.Size(); sz > int64(c.RecipeResultByteLimit) {
			return fail(errors.Reason("recipe result file is %d bytes which is more than %d",
				sz, c.RecipeResultByteLimit).Err())
		}
	}

	result.RecipeResult = &recipe_engine.Result{}
	err = (&jsonpb.Unmarshaler{
		AllowUnknownFields: true,
	}).Unmarshal(recipeResultFile, result.RecipeResult)
	if err != nil {
		return fail(errors.Annotate(err, "could not parse recipe result").Err())
	}

	// TODO(nodir): remove result.
	if result.RecipeResult.GetFailure() != nil && result.RecipeResult.GetFailure().GetFailure() == nil {
		// The recipe run has failed and the failure type is not step failure.
		result.InfraFailure = &build.InfraFailure{
			Text: fmt.Sprintf("recipe infra failure: %s", result.RecipeResult.GetFailure().HumanReason),
			Type: build.InfraFailure_RECIPE_INFRA_FAILURE,
		}
		return result
	}

	return result
}

// pathModuleProperties returns properties for the "recipe_engine/path" module.
func (c *cookRun) pathModuleProperties() (map[string]string, error) {
	recipeTempDir := filepath.Join(c.TempDir, "rt")
	if err := ensureDir(recipeTempDir); err != nil {
		return nil, err
	}
	paths := []struct{ name, path string }{
		{"cache_dir", c.CacheDir},
		{"temp_dir", recipeTempDir},
	}

	props := make(map[string]string, len(paths))
	for _, p := range paths {
		if p.path == "" {
			continue
		}
		native := filepath.FromSlash(p.path)
		if err := filesystem.AbsPath(&native); err != nil {
			return nil, err
		}
		props[p.name] = native
	}

	return props, nil
}

// prepareProperties parses the properties specified by flags, validates them,
// add some extra properties to describe current build environment and pops
// properties consumed specifically by kitchen.
//
// May mutate some other properties too.
func (c *cookRun) prepareProperties(env environ.Env) (map[string]interface{}, *kitchenProperties, error) {
	props, err := parseProperties(c.Properties, c.PropertiesFile)
	if err != nil {
		return nil, nil, errors.Annotate(err, "could not parse properties").Err()
	}
	if props == nil {
		props = map[string]interface{}{}
	}

	// Reject reserved properties.
	rejectProperties := []string{
		"$recipe_engine/path",
		"$recipe_engine/step",
		"bot_id",
		// not specifying path_config means that all paths must be passed
		// explicitly. We do that below.
		"path_config",
	}
	for _, p := range rejectProperties {
		if _, ok := props[p]; ok {
			return nil, nil, inputError("%s property must not be set", p)
		}
	}

	// Configure paths that the recipe will use.
	pathProps, err := c.pathModuleProperties()
	if err != nil {
		return nil, nil, err
	}
	props["$recipe_engine/path"] = pathProps

	// Use "generic" infra path config. See
	// https://chromium.googlesource.com/chromium/tools/depot_tools/+/master/recipes/recipe_modules/infra_paths/
	props["path_config"] = "generic"

	botID, ok := env.Get("SWARMING_BOT_ID")
	if !ok {
		return nil, nil, inputError("no Swarming bot ID in $SWARMING_BOT_ID")
	}
	props["bot_id"] = botID

	// Extract "$kitchen" properties into more usable struct.
	kitchenProps := &kitchenProperties{
		GitAuth:      true,
		DevShell:     true,
		DockerAuth:   true,
		FirebaseAuth: false,
	}
	if val, _ := props["$kitchen"]; val != nil {
		blob, err := json.Marshal(val)
		if err != nil {
			return nil, nil, errors.Annotate(err, "impossible serialization error").Err()
		}
		if err := json.Unmarshal(blob, kitchenProps); err != nil {
			return nil, nil, errors.Annotate(err, "failed to deserialize $kitchen properties").Err()
		}
	}
	delete(props, "$kitchen")

	return props, kitchenProps, nil
}

func (c *cookRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	// The first thing we do is write a result file in case we crash or get killed.
	// Note that this code is not reachable if subcommands package could not
	// parse flags.
	result := &build.BuildRunResult{
		InfraFailure: &build.InfraFailure{
			Type: build.InfraFailure_BOOTSTRAPPER_ERROR,
			Text: "kitchen crashed or got killed",
		},
	}
	if err := c.flushResult(result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	ctx := cli.GetContext(a, c, env)
	sysEnv := environ.System()

	result = c.run(ctx, args, sysEnv)
	fmt.Println(strings.Repeat("-", 35), "RESULTS", strings.Repeat("-", 36))
	proto.MarshalText(os.Stdout, result)
	fmt.Println(strings.Repeat("-", 80))

	if err := c.flushResult(result); err != nil {
		fmt.Fprintf(os.Stderr, "could not flush result to a file: %s\n", err)
		return 1
	}

	if result.InfraFailure != nil {
		fmt.Fprintln(os.Stderr, "run failed because of an infra failure")
		return 1
	}
	if result.RecipeExitCode == nil {
		panic("impossible: InfraFailure is nil, but there is no recipe exit code")
	}
	return int(result.RecipeExitCode.Value)
}

// run runs the cook subcommmand and returns cook result.
func (c *cookRun) run(ctx context.Context, args []string, env environ.Env) *build.BuildRunResult {
	fail := func(err error) *build.BuildRunResult {
		return &build.BuildRunResult{InfraFailure: infraFailure(err)}
	}

	// If we are asked to call UpdateBuild, prepare a buildUpdater.
	if c.CallUpdateBuild {
		var err error
		c.bu, err = c.newBuildUpdater()
		if err != nil {
			return fail(errors.Annotate(err, "failed to create a build updater").Err())
		}
	}

	// Process input.
	if len(args) != 0 {
		return fail(inputError("unexpected arguments: %v", args))
	}
	if _, err := os.Getwd(); err != nil {
		return fail(inputError("failed to resolve CWD: %s", err))
	}
	if err := c.normalizeFlags(); err != nil {
		return fail(err)
	}

	// initialize temp dir.
	if c.TempDir == "" {
		tdir, err := ioutil.TempDir("", "kitchen")
		if err != nil {
			return fail(errors.Annotate(err, "failed to create temporary directory").Err())
		}
		c.TempDir = tdir
		defer func() {
			if rmErr := os.RemoveAll(tdir); rmErr != nil {
				log.Warningf(ctx, "Failed to clean up temporary directory at [%s]: %s", tdir, rmErr)
			}
		}()
	}

	// Prepare recipe properties. Print them too.
	var err error
	if c.engine.properties, c.kitchenProps, err = c.prepareProperties(env); err != nil {
		return fail(err)
	}
	if err := c.reportProperties(ctx, "recipe engine", c.engine.properties); err != nil {
		return fail(err)
	}
	if err := c.reportProperties(ctx, "kitchen", c.kitchenProps); err != nil {
		return fail(err)
	}

	if err := c.updateEnv(&env); err != nil {
		return fail(errors.Annotate(err, "failed to update the environment").Err())
	}

	// Make kitchen use the new $PATH too. This is needed for exec.LookPath called
	// by kitchen to pick up binaries in the modified $PATH. In practice, we do it
	// so that kitchen uses the installed git wrapper.
	//
	// All other env modifications must be performed using 'env' object.
	path, _ := env.Get("PATH")
	if err := os.Setenv("PATH", path); err != nil {
		return fail(errors.Annotate(err, "failed to update process PATH").Err())
	}

	// Read BuildSecrets message from swarming secret bytes.
	if c.buildSecrets, err = readBuildSecrets(ctx); err != nil {
		return fail(errors.Annotate(err, "failed to read build secrets").Err())
	}

	// Create systemAuth and recipeAuth authentication contexts, since we are
	// about to start making authenticated requests now.
	if err := c.setupAuth(ctx, c.kitchenProps.GitAuth, c.kitchenProps.DevShell, c.kitchenProps.DockerAuth, c.kitchenProps.FirebaseAuth); err != nil {
		return fail(errors.Annotate(err, "failed to setup auth").Err())
	}
	defer c.recipeAuth.Close()
	defer c.systemAuth.Close()

	// Run the recipe.
	result := c.runRecipe(ctx, env)

	// Make a final UpdateBuild call.
	if c.bu != nil {
		// The final UpdateBuild call is critical.
		// If it fails, it is fatal to the build.

		req, err := c.bu.ParseAnnotations(ctx, result.Annotations)
		if err != nil {
			return fail(errors.Annotate(err, "failed to parse final annotations").Err())
		}

		// If the build failed, update the build status.
		// If it suceeded, do not set it just yet, since there are more ways
		// the swarming task can fail.
		switch {
		case result.InfraFailure != nil:
			req.Build.Status = buildbucketpb.Status_INFRA_FAILURE
			req.Build.SummaryMarkdown = result.InfraFailure.Text
			req.UpdateMask.Paths = append(req.UpdateMask.Paths, "build.status", "build.summary_markdown")

		case result.RecipeResult.GetFailure() != nil:
			// Note: if this recipe failure is an infra failure,
			// result.InfraFailure above is non-nil.
			req.Build.Status = buildbucketpb.Status_FAILURE
			req.Build.SummaryMarkdown = result.RecipeResult.GetFailure().HumanReason
			req.UpdateMask.Paths = append(req.UpdateMask.Paths, "build.status", "build.summary_markdown")
		}

		if err := c.bu.UpdateBuild(ctx, req); err != nil {
			return fail(errors.Annotate(err, "failed to send final build state to buildbucket").Err())
		}
	}

	return result
}

// flushResult writes the result to c.OutputResultJSOPath file
// if the path is specified.
func (c *cookRun) flushResult(result *build.BuildRunResult) (err error) {
	if c.OutputResultJSONPath == "" {
		return nil
	}

	defer func() {
		if err != nil {
			err = errors.Annotate(err, "could not write result file at %q", c.OutputResultJSONPath).Err()
		}
	}()

	f, err := os.Create(c.OutputResultJSONPath)
	if err != nil {
		return err
	}
	defer func() {
		err = f.Close()
		if err != nil {
			err = errors.Annotate(err, "could not close file").Err()
		}
	}()
	m := jsonpb.Marshaler{EmitDefaults: true}
	return m.Marshal(f, result)
}

// updateEnv updates temp path env variables in env.
func (c *cookRun) updateEnv(env *environ.Env) error {
	if c.TempDir == "" {
		// It should have been initialized in c.run.
		panic("TempDir was not initialized earlier")
	}
	// Tell subprocesses to use a subdirectory in Kitchen's temp dir. Note that
	// we can't use TempDir directly because some overzealous scripts like to
	// remove everything they find under TEMPDIR, and it breaks Kitchen internals
	// that keep some files in c.TempDir (in particular git and gsutil configs
	// setup by AuthContext).
	tmp := filepath.Join(c.TempDir, "t")
	if err := os.Mkdir(tmp, 0700); err != nil && !os.IsExist(err) {
		return errors.Annotate(err, "failed to create temp dir for the task (%s)", tmp).Err()
	}
	for _, v := range []string{"TEMPDIR", "TMPDIR", "TEMP", "TMP", "MAC_CHROMIUM_TMPDIR"} {
		env.Set(v, tmp)
	}
	return nil
}

// reportProperties serializes to JSON and logs given properties.
func (c *cookRun) reportProperties(ctx context.Context, realm string, props interface{}) error {
	propsJSON, err := json.MarshalIndent(props, "", "  ")
	if err != nil {
		return errors.Annotate(err, "could not marshal properties to JSON").Err()
	}
	log.Infof(ctx, "using %s properties:\n%s", realm, propsJSON)
	return nil
}

// setupAuth prepares systemAuth and recipeAuth contexts based on incoming
// environment and command line flags.
func (c *cookRun) setupAuth(ctx context.Context, enableGitAuth, enableDevShell, enableDockerAuth, enableFirebaseAuth bool) error {
	// If we are given -luci-system-account flag, use the corresponding logical
	// account if it's in the LUCI_CONTEXT (fail if not).
	//
	// Otherwise, we run Kitchen with whatever is default account now (don't
	// switch to a system one). Happens when running Kitchen manually locally. It
	// picks up the developer account.
	systemAuth := &AuthContext{
		ID:                 "system",
		EnableGitAuth:      enableGitAuth,
		EnableDevShell:     enableDevShell,
		EnableDockerAuth:   enableDockerAuth,
		EnableFirebaseAuth: enableFirebaseAuth,
		KnownGerritHosts:   c.KnownGerritHost,
	}
	switch {
	case c.SystemAccount != "":
		la := lucictx.GetLocalAuth(ctx)
		if la == nil {
			return errors.New("can't use -luci-system-account, no local_auth in LUCI_CONTEXT")
		}
		for _, acc := range la.Accounts {
			if acc.ID == c.SystemAccount {
				la.DefaultAccountID = c.SystemAccount // use it by default
				systemAuth.LocalAuth = la
				break
			}
		}
		if systemAuth.LocalAuth == nil {
			return errors.Reason("can't change system account, no such logical account %q in LUCI_CONTEXT", c.SystemAccount).Err()
		}
	default:
		systemAuth.LocalAuth = lucictx.GetLocalAuth(ctx)
	}

	// Recipes always use the account that is set as default when kitchen starts
	// (it is a task-associated account on Swarming). So just grab the current
	// LUCI_CONTEXT["local_auth"] and retain it for recipes.
	recipeAuth := &AuthContext{
		ID:                 "task",
		LocalAuth:          lucictx.GetLocalAuth(ctx),
		EnableGitAuth:      enableGitAuth,
		EnableDevShell:     enableDevShell,
		EnableDockerAuth:   enableDockerAuth,
		EnableFirebaseAuth: enableFirebaseAuth,
		KnownGerritHosts:   c.KnownGerritHost,
	}

	// Launching the auth context may create files or start background goroutines.
	if err := systemAuth.Launch(ctx, c.TempDir); err != nil {
		return errors.Annotate(err, "failed to start system auth context").Err()
	}
	if err := recipeAuth.Launch(ctx, c.TempDir); err != nil {
		systemAuth.Close() // best effort cleanup
		return errors.Annotate(err, "failed to start recipe auth context").Err()
	}

	// Log the actual service account emails corresponding to each context.
	systemAuth.ReportServiceAccount()
	recipeAuth.ReportServiceAccount()
	c.systemAuth = systemAuth
	c.recipeAuth = recipeAuth

	return nil
}

// globalTags returns tags to be applied to all logdog streams by default.
func (c *cookRun) globalTags(env environ.Env) map[string]string {
	ret := make(map[string]string, len(c.GlobalLogDogTags)+1)
	if c.BuildURL != "" {
		ret[logDogViewerURLTag] = c.BuildURL
	}

	// SWARMING_SERVER is the full URL: https://example.com
	// We want just the hostname.
	if v, ok := env.Get("SWARMING_SERVER"); ok {
		if u, err := url.Parse(v); err == nil && u.Host != "" {
			ret["swarming.host"] = u.Host
		}
	}
	if v, ok := env.Get("SWARMING_TASK_ID"); ok {
		ret["swarming.run_id"] = v
	}
	if v, ok := env.Get("SWARMING_BOT_ID"); ok {
		ret["bot_id"] = v
	}

	// Prefer user-supplied tags to our generated ones.
	for k, v := range c.GlobalLogDogTags {
		ret[k] = v
	}

	return ret
}

// butlerOutput creates LogDog output destination.
// The caller is responsible for closing it.
func (c *cookRun) butlerOutput(ctx context.Context) (output.Output, error) {
	if c.LogFilePath != "" {
		// Debug: Use a file output.
		ocfg := fileOut.Options{Path: c.LogFilePath}
		return ocfg.New(ctx), nil
	}

	prefix, _ := c.AnnotationURL.Path.Split()
	ocfg := out.Config{
		Auth:           c.systemAuth.Authenticator(),
		Host:           c.AnnotationURL.Host,
		Project:        c.AnnotationURL.Project,
		Prefix:         prefix,
		SourceInfo:     []string{"Kitchen"},
		RPCTimeout:     defaultRPCTimeout,
		PublishContext: withNonCancel(ctx),
	}
	return ocfg.Register(ctx)
}

func (c *cookRun) newButler(ctx context.Context, out output.Output, env environ.Env) (*butler.Butler, error) {
	prefix, _ := c.AnnotationURL.Path.Split()
	cfg := butler.Config{
		Output:       out,
		Project:      c.AnnotationURL.Project,
		Prefix:       prefix,
		BufferLogs:   true,
		MaxBufferAge: butler.DefaultMaxBufferAge,
		GlobalTags:   c.globalTags(env),
	}
	return butler.New(ctx, cfg)
}

// runWithLogdogButler runs the supplied command through the a LogDog Butler
// engine instance. This involves:
//	- Configuring / setting up the Butler.
//	- Initiating a LogDog Pub/Sub Output, registering with remote server.
//	- Running the recipe process.
//	- Hook its output streams up through an Annotee processor.
//	- Wait for the subprocess to finish.
//	- Shut down the Butler instance.
// Writes res.RecipeExitCode and res.Annotations on success.
func (c *cookRun) runWithLogdogButler(ctx context.Context, env environ.Env, res *build.BuildRunResult) (err error) {
	log.Infof(ctx, "Using LogDog URL: %s", &c.AnnotationURL)

	// Install a global gRPC logger adapter. This routes gRPC log messages that
	// are emitted through our logger. We only log gRPC prints if our logger is
	// configured to log debug-level or lower.
	disableGRPCLogging(ctx)

	// Create our stream server instance.
	streamServer, err := c.getLogDogStreamServer(withNonCancel(ctx))
	if err != nil {
		return errors.Annotate(err, "failed to generate stream server").Err()
	}

	if err := streamServer.Listen(); err != nil {
		return errors.Annotate(err, "failed to listen on stream server").Err()
	}
	defer func() {
		if streamServer != nil {
			streamServer.Close()
		}
	}()

	log.Debugf(ctx, "Generated stream server at: %s", streamServer.Address())

	// Use the annotation stream's prefix component for our Butler run.
	prefix, annoName := c.AnnotationURL.Path.Split()

	// Augment our environment with Butler parameters.
	bsEnv := bootstrap.Environment{
		Project:         c.AnnotationURL.Project,
		Prefix:          prefix,
		StreamServerURI: streamServer.Address(),
		CoordinatorHost: c.AnnotationURL.Host,
	}
	bsEnv.Augment(env)

	// Create a Butler.
	butlerOutput, err := c.butlerOutput(ctx)
	if err != nil {
		return errors.Annotate(err, "failed to create LogDog Output instance").Err()
	}
	defer butlerOutput.Close()
	b, err := c.newButler(withNonCancel(ctx), butlerOutput, env)
	if err != nil {
		return errors.Annotate(err, "failed to create Butler instance").Err()
	}
	defer func() {
		b.Activate()
		if ierr := b.Wait(); ierr != nil {
			ierr = errors.Annotate(ierr, "failed to Wait() for Butler").Err()
			logAnnotatedErr(ctx, ierr)

			// Promote to function output error if we don't have one yet.
			if err == nil {
				err = ierr
			}
		}
	}()

	b.AddStreamServer(streamServer)
	streamServer = nil

	// Start our bootstrapped subprocess.
	//
	// We need to consume all of its streams prior to waiting for completion (see
	// exec.Cmd).
	//
	// We'll set up our own cancellation function to help ensure that the process
	// is properly terminated regardless of any encountered errors.
	procCtx, procCancelFunc := context.WithCancel(ctx)
	defer procCancelFunc()

	proc, err := c.engine.commandRun(procCtx, filepath.Join(c.TempDir, "rr"), env)
	if err != nil {
		return errors.Annotate(err, "failed to build recipe command").Err()
	}

	// Build pipes for our STDOUT and STDERR streams.
	stdout, err := proc.StdoutPipe()
	if err != nil {
		return errors.Annotate(err, "failed to get STDOUT pipe").Err()
	}
	defer stdout.Close()

	stderr, err := proc.StderrPipe()
	if err != nil {
		return errors.Annotate(err, "failed to get STDERR pipe").Err()
	}
	defer stderr.Close()

	// Start our bootstrapped subprocess.
	printCommand(ctx, proc)
	if err = proc.Start(); err != nil {
		return errors.Annotate(err, "failed to start command").Err()
	}

	// While the subprocess runs, continuously read its output.
	execMetadata := annotation.ProbeExecution(proc.Args, proc.Env, proc.Dir)
	if res.Annotations, err = c.watchSubprocessOutput(ctx, annoName, stdout, stderr, execMetadata, b, procCancelFunc); err != nil {
		log.Errorf(ctx, "failed to read subprocess output: %s", err)
		log.Errorf(ctx, "killing it and waiting for it to die")
		procCancelFunc()
		// do not let the subprocess outlive this one.
		if werr := proc.Wait(); werr != nil {
			log.Errorf(ctx, "the subprocess died: %s", werr)
		}

		return errors.Annotate(err, "failed to read subprocess output").Err()
	}

	// Wait for the subprocess to finish.
	// Most likely it already finished because watching stops when stdout/stderr
	// are closed.
	waitErr := proc.Wait()
	switch waitRC, hasRC := exitcode.Get(waitErr); {
	case hasRC:
		log.Warningf(ctx, "subprocess exited with code %d", waitRC)
		res.RecipeExitCode = &build.OptionalInt32{Value: int32(waitRC)}
	case waitErr != nil:
		return errors.Annotate(waitErr, "failed to Wait() for process").Err()
	}

	return nil
}

// watchSubprocessOutput annotates stdout/stderr and writes the annotation
// messages to a stream, and optionally sends build info to Buildbucket server
// (if c.CallUpdateBuild is true).
func (c *cookRun) watchSubprocessOutput(ctx context.Context, annStreamName types.StreamName, stdout, stderr io.Reader, execMetadata *annotation.Execution, b *butler.Butler, stopSubprocess func()) (build *milo.Step, err error) {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Determine our base path and annotation subpath.
	basePath, annoSubpath := annStreamName.Split()
	annoteeOpts := annotee.Options{
		Base:                   basePath,
		AnnotationSubpath:      annoSubpath,
		Client:                 localclient.New(b),
		Execution:              execMetadata,
		MetadataUpdateInterval: 30 * time.Second,
		Offline:                false,
		CloseSteps:             true,
	}

	var stopBU func() error
	if c.bu != nil {
		annoteeOpts.AnnotationUpdated = c.bu.AnnotationUpdated

		errC := make(chan error)
		done := make(chan struct{})
		stopBU = func() error {
			close(done)
			return <-errC
		}
		go func() {
			err := c.bu.Run(ctx, done)
			if err != nil {
				log.Errorf(ctx, "build runner failed; killing the subprocess: %s", err)
				stopSubprocess()
			}
			errC <- err
		}()
	}

	annoteeProcessor := annotee.New(withNonCancel(ctx), annoteeOpts)

	// Run STDOUT/STDERR streams through the processor.
	streams := []*annotee.Stream{
		{
			Reader:   stdout,
			Name:     annotee.STDOUT,
			Annotate: true,
		},
		{
			Reader:   stderr,
			Name:     annotee.STDERR,
			Annotate: true,
		},
	}

	// Run the process' output streams through Annotee. This will block until
	// they are all consumed.
	if err := annoteeProcessor.RunStreams(streams); err != nil {
		return nil, errors.Annotate(err, "failed to process streams through Annotee").Err()
	}

	// Stop the build updater, if any.
	if stopBU != nil {
		if err := stopBU(); err != nil {
			return nil, errors.Annotate(err, "build updater failed").Err()
		}
	}

	// Read the final annotation.
	return annoteeProcessor.Finish().RootStep().Proto(), nil
}

// newBuildUpdater creates a buildUpdater that uses system auth for RPCs.
func (c *cookRun) newBuildUpdater() (*buildUpdater, error) {
	httpClient, err := c.systemAuth.Authenticator().Client()
	if err != nil {
		return nil, errors.Annotate(err, "failed to create a system-auth HTTP client for updating build state on the server").Err()
	}
	return &buildUpdater{
		annAddr:    &c.AnnotationURL,
		buildID:    c.BuildbucketBuildID,
		buildToken: c.buildSecrets.BuildToken,
		client: buildbucketpb.NewBuildsPRPCClient(&prpc.Client{
			Host: c.BuildbucketHostname,
			C:    httpClient,
		}),
		annotations: make(chan []byte),
	}, nil
}

// getLogDogStreamServer returns a LogDog stream server instance configured for
// the current operating system.
//
// Because Windows doesn't have UNIX domain sockets, and Linux doesn't have
// named pipes, this becomes platform-specific.
func (c *cookRun) getLogDogStreamServer(ctx context.Context) (streamserver.StreamServer, error) {
	return getLogDogStreamServerForPlatform(ctx, c.TempDir)
}

func parseProperties(properties map[string]interface{}, propertiesFile string) (result map[string]interface{}, err error) {
	if len(properties) > 0 {
		return properties, nil
	}
	if propertiesFile != "" {
		b, err := ioutil.ReadFile(propertiesFile)
		if err != nil {
			err = inputError("could not read properties file %s\n%s", propertiesFile, err)
			return nil, err
		}
		err = json.Unmarshal(b, &result)
		if err != nil {
			err = inputError("could not parse JSON from file %s\n%s\n%s",
				propertiesFile, b, err)
		}
	}
	return
}

func setAnnotationText(s *milo.Step) {
	// TODO(nodir,iaanucci): clean this up when we define a new UI proto
	s.Text = nil
	for _, substep := range s.Substep {
		ss := substep.GetStep()
		if ss != nil && ss.Status == milo.Status_FAILURE && ss.Name != "Failure reason" {
			s.Text = append(s.Text, fmt.Sprintf("Failure %s", ss.Name))
		}
	}
}
