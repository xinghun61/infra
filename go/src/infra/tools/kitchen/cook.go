// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	log "go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/milo"
	"go.chromium.org/luci/common/system/environ"
	"go.chromium.org/luci/common/system/exitcode"
	"go.chromium.org/luci/common/system/filesystem"
	"go.chromium.org/luci/lucictx"

	"infra/tools/kitchen/build"
	"infra/tools/kitchen/cookflags"
	"infra/tools/kitchen/third_party/recipe_engine"
)

// BootstrapStepName is the name of kitchen's step where it makes preparations
// for running a recipe, e.g. fetches a repository.
const BootstrapStepName = "recipe bootstrap"

// cmdCook checks out a repository at a revision and runs a recipe.
var cmdCook = &subcommands.Command{
	UsageLine: "cook -repository <repository URL> -recipe <recipe>",
	ShortDesc: "bootstraps a LUCI job.",
	LongDesc:  "Bootstraps a LUCI job.",
	CommandRun: func() subcommands.CommandRun {
		var c cookRun

		// Initialize our AnnotationFlags operational argument.
		c.engine.opArgs.AnnotationFlags = &recipe_engine.Arguments_AnnotationFlags{}
		c.engine.opArgs.EngineFlags = &recipe_engine.Arguments_EngineFlags{}

		c.CookFlags.Register(&c.Flags)

		return &c
	},
}

type cookRun struct {
	subcommands.CommandRunBase

	cookflags.CookFlags

	mode         cookMode
	engine       recipeEngine
	kitchenProps *kitchenProperties

	systemAuth *AuthContext // used by kitchen itself for logdog, bigquery, git
	recipeAuth *AuthContext // used by the recipe

	// testRun is set to true during testing to instruct Kitchen not to try and
	// send monitoring events.
	testRun bool
}

// kitchenProperties defines the structure of "$kitchen" build property.
//
// It is consumed exclusively by Kitchen and not even passed along to the recipe
// engine.
type kitchenProperties struct {
	GitAuth bool `json:"git_auth"`
}

// normalizeFlags validates and normalizes flags.
func (c *cookRun) normalizeFlags() error {
	if err := c.CookFlags.Normalize(); err != nil {
		return err
	}

	c.mode = cookModeSelector[c.Mode]
	c.engine.workDir = c.WorkDir
	c.engine.recipeName = c.RecipeName

	return nil
}

// ensureAndRunRecipe ensures that we have the recipe (according to -repository,
// -revision and -checkout-dir) and all its deps and runs it.
func (c *cookRun) ensureAndRunRecipe(ctx context.Context, env environ.Env) *build.BuildRunResult {
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

	if c.RepositoryURL == "" {
		// The ready-to-run recipe is already present on the file system.
		recipesPath, err := exec.LookPath(filepath.Join(c.CheckoutDir, "recipes"))
		if err != nil {
			return fail(errors.Annotate(err, "could not find bundled recipes").Err())
		}
		c.engine.cmdPrefix = []string{recipesPath}
	} else {
		// Run initial git fetch in system account context (which is always present
		// on bots), since recipes bootstrap is considered part of the overall
		// "Recipes on Swarming" offering. Users that run recipes on Swarming
		// expect the recipe to actually start, even if their task is not associated
		// with a service account (the recipe runs in anonymous context in this
		// case).
		sysEnv := c.systemAuth.ExportIntoEnv(env)

		// Fetch the recipe. Record the fetched revision.
		rev, err := checkoutRepository(ctx, sysEnv, c.CheckoutDir, c.RepositoryURL, c.Revision)
		if err != nil {
			return fail(errors.Annotate(err, "could not checkout %q at %q to %q",
				c.RepositoryURL, c.Revision, c.CheckoutDir).Err())
		}

		result.Recipe.Repository = c.RepositoryURL
		result.Recipe.Revision = rev

		// Record the fetched repository. Add ".git" if it doesn't have it
		// (normalization).
		if !strings.HasSuffix(result.Recipe.Repository, ".git") {
			result.Recipe.Repository += ".git"
		}

		// Read the path to the recipes.py within the fetched repo.
		recipesPath, err := getRecipesPath(c.CheckoutDir)
		if err != nil {
			return fail(errors.Annotate(err, "could not read recipes.cfg").Err())
		}
		c.engine.cmdPrefix = []string{
			"python",
			filepath.Join(c.CheckoutDir, filepath.FromSlash(recipesPath), "recipes.py"),
		}

		// Fetch all recipe dependencies. They are fetched into some internal guts
		// controlled by the engine (not a work dir). So we can do it before setting
		// up the work dir.
		if err := c.engine.fetchRecipeDeps(ctx, sysEnv); err != nil {
			return fail(errors.Annotate(err, "failed to fetch recipe deps").Err())
		}
	}

	// Setup our working directory. This is cwd for the recipe itself.
	var err error
	c.engine.workDir, err = prepareRecipeRunWorkDir(c.engine.workDir)
	if err != nil {
		return fail(errors.Annotate(err, "failed to prepare workdir").Err())
	}

	// Tell the recipe to write the result protobuf message to a file and read
	// it below.
	c.engine.opArgs.EngineFlags.UseResultProto = true
	c.engine.outputResultJSONFile = filepath.Join(c.TempDir, "recipe-result.json")

	// Run the recipe in the appropriate auth context by exporting it into the
	// environ of the recipe engine.
	recipeEnv := c.recipeAuth.ExportIntoEnv(env)

	rv := 0
	if c.CookFlags.LogDogFlags.Active() {
		result.AnnotationUrl = c.CookFlags.LogDogFlags.AnnotationURL.String()
		rv, result.Annotations, err = c.runWithLogdogButler(ctx, &c.engine, recipeEnv)
		if err != nil {
			return fail(errors.Annotate(err, "failed to run recipe").Err())
		}
		setAnnotationText(result.Annotations)
	} else {
		// This code is reachable only in buildbot mode.
		recipeCmd, err := c.engine.commandRun(ctx, filepath.Join(c.TempDir, "rr"), recipeEnv)
		if err != nil {
			return fail(errors.Annotate(err, "failed to build recipe run command").Err())
		}
		printCommand(ctx, recipeCmd)

		recipeCmd.Stdout = os.Stdout
		recipeCmd.Stderr = os.Stderr

		err = recipeCmd.Run()
		var hasRV bool
		rv, hasRV = exitcode.Get(err)
		if !hasRV {
			return fail(errors.Annotate(err, "failed to run recipe").Err())
		}
	}
	result.RecipeExitCode = &build.OptionalInt32{Value: int32(rv)}

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

	// TODO(nodir): verify consistency between result.Build and result.RecipeResult.

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

// stepModuleProperties are constructed properties for the "recipe_engine/step"
// recipe module.
type stepModuleProperties struct {
	PrefixPATH []string `json:"prefix_path,omitempty"`
}

// stepModuleProperties returns properties for the "recipe_engine/step" module.
func (c *cookRun) stepModuleProperties() *stepModuleProperties {
	if len(c.PrefixPathENV) == 0 {
		return nil
	}

	return &stepModuleProperties{
		PrefixPATH: []string(c.PrefixPathENV),
	}
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

	if p := c.stepModuleProperties(); p != nil {
		props["$recipe_engine/step"] = p
	}

	// Use "generic" infra path config. See
	// https://chromium.googlesource.com/chromium/tools/depot_tools/+/master/recipes/recipe_modules/infra_paths/
	props["path_config"] = "generic"

	if err := c.mode.addProperties(props, env); err != nil {
		return nil, nil, errors.Annotate(err, "chosen mode could not add properties").Err()
	}
	if _, ok := props[PropertyBotID]; !ok {
		return nil, nil, errors.Reason("chosen mode didn't add %s property", PropertyBotID).Err()
	}

	// Extract "$kitchen" properties into more usable struct.
	kitchenProps := &kitchenProperties{}
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
	mon := Monitoring{}
	mon.beginExecution(ctx)

	fail := func(err error) *build.BuildRunResult {
		return &build.BuildRunResult{InfraFailure: infraFailure(err)}
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

	// If we're not using LogDog, send out annotations.
	bootstrapSuccess := false
	if c.CookFlags.LogDogFlags.ShouldEmitAnnotations() {
		// This code is reachable only in buildbot mode.

		annotate := func(args ...string) {
			fmt.Printf("@@@%s@@@\n", strings.Join(args, "@"))
		}
		annotate("SEED_STEP", BootstrapStepName)
		annotate("STEP_CURSOR", BootstrapStepName)
		annotate("STEP_STARTED")
		defer func() {
			annotate("STEP_CURSOR", BootstrapStepName)
			if bootstrapSuccess {
				annotate("STEP_CLOSED")
			} else {
				annotate("STEP_EXCEPTION")
			}
		}()

		for k, v := range c.engine.properties {
			// Order is not stable, but that is okay.
			jv, err := json.Marshal(v)
			if err != nil {
				return fail(errors.Annotate(err, "").Err())
			}
			annotate("SET_BUILD_PROPERTY", k, string(jv))
		}
	}

	c.updateEnv(env)

	// Make kitchen use the new $PATH too. This is needed for exec.LookPath called
	// by kitchen to pick up binaries in the modified $PATH. In practice, we do it
	// so that kitchen uses the installed git wrapper.
	//
	// All other env modifications must be performed using 'env' object.
	path, _ := env.Get("PATH")
	if err := os.Setenv("PATH", path); err != nil {
		return fail(errors.Annotate(err, "failed to update process PATH").Err())
	}

	// Create systemAuth and recipeAuth authentication contexts, since we are
	// about to start making authenticated requests now.
	if err := c.setupAuth(ctx, c.kitchenProps.GitAuth); err != nil {
		return fail(errors.Annotate(err, "failed to setup auth").Err())
	}
	defer c.recipeAuth.Close()
	defer c.systemAuth.Close()

	// Run the recipe.
	result := c.ensureAndRunRecipe(ctx, env)

	// Send our "build completed" monitoring event. If this fails, we will log
	// the failure, but it is non-fatal.
	mon.endExecution(ctx, result)
	if !c.testRun {
		if err := mon.SendBuildCompletedReport(ctx, c.systemAuth); err != nil {
			log.Errorf(ctx, "Failed to send 'build completed' monitoring report: %s", err)
		}
	}

	bootstrapSuccess = result.InfraFailure == nil
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

// updateEnv updates $PATH, $PYTHONPATH and temp path env variables in env.
func (c *cookRun) updateEnv(env environ.Env) {
	addPaths := func(key string, paths []string) {
		if len(paths) == 0 {
			return
		}
		cur, _ := env.Get(key)
		all := make([]string, 0, len(paths)+1)
		all = append(all, paths...)
		if len(cur) > 0 {
			all = append(all, cur)
		}
		env.Set(key, strings.Join(all, string(os.PathListSeparator)))
	}

	addPaths("PATH", c.PrefixPathENV)

	env.Load(c.SetEnvAbspath)

	// Tell subprocesses to use Kitchen's temp dir.
	if c.TempDir == "" {
		// It should have been initialized in c.run.
		panic("TempDir was not initialzied earlier")
	}
	for _, v := range []string{"TEMPDIR", "TMPDIR", "TEMP", "TMP", "MAC_CHROMIUM_TMPDIR"} {
		env.Set(v, c.TempDir)
	}
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
func (c *cookRun) setupAuth(ctx context.Context, enableGitAuth bool) error {
	// Don't mess with git authentication in Buildbot mode, it won't work without
	// proper LUCI_CONTEXT environment.
	if enableGitAuth && !c.mode.allowCustomGitAuth() {
		log.Warningf(ctx, "Git authentication is not supported in the current mode")
		enableGitAuth = false
	}

	// If we are explicitly given a system account JSON key, use it for Kitchen.
	// This happens when Kitchen is used from BuildBot ("LUCI Emulation Mode").
	//
	// Otherwise, if we are given -luci-system-account flag, use the corresponding
	// logical account if it's in the LUCI_CONTEXT (fail if not). This is what's
	// used on Swarming.
	//
	// And if neither are given run Kitchen with whatever is default account now
	// (don't switch to a system one). Happens when running Kitchen manually
	// locally. It picks up the developer account.
	systemAuth := &AuthContext{
		ID:               "system",
		EnableGitAuth:    enableGitAuth,
		KnownGerritHosts: c.KnownGerritHost,
	}
	switch {
	case c.SystemAccountJSON != "":
		if c.SystemAccount != "" {
			return errors.New("-luci-system-account and -luci-system-account-json shouldn't be used together")
		}
		systemAuth.ServiceAccountJSONPath = c.SystemAccountJSON
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
			return errors.New(fmt.Sprintf("can't change system account, no such logical account %q in LUCI_CONTEXT", c.SystemAccount))
		}
	default:
		systemAuth.LocalAuth = lucictx.GetLocalAuth(ctx)
	}

	// Recipes always use the account that is set as default when kitchen starts
	// (it is a task-associated account on Swarming). So just grab the current
	// LUCI_CONTEXT["local_auth"] and retain it for recipes.
	recipeAuth := &AuthContext{
		ID:               "task",
		LocalAuth:        lucictx.GetLocalAuth(ctx),
		EnableGitAuth:    enableGitAuth,
		KnownGerritHosts: c.KnownGerritHost,
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
		err = unmarshalJSONWithNumber(b, &result)
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
