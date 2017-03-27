// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/flag/stringlistflag"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/common/system/exitcode"

	"infra/tools/kitchen/migration"
	"infra/tools/kitchen/proto"
)

// BootstrapStepName is the name of kitchen's step where it makes preparations
// for running a recipe, e.g. fetches a repository.
const BootstrapStepName = "recipe bootstrap"

// cmdCook checks out a repository at a revision and runs a recipe.
var cmdCook = &subcommands.Command{
	UsageLine: "cook -repository <repository URL> -recipe <recipe>",
	ShortDesc: "bootstraps a swarmbucket job.",
	LongDesc:  "Bootstraps a swarmbucket job.",
	CommandRun: func() subcommands.CommandRun {
		var c cookRun

		// Initialize our AnnotationFlags operational argument.
		c.rr.opArgs.AnnotationFlags = &recipe_engine.Arguments_AnnotationFlags{}
		c.rr.opArgs.EngineFlags = &recipe_engine.Arguments_EngineFlags{
			UseResultProto: true,
		}

		fs := &c.Flags
		fs.Var(&c.mode,
			"mode",
			"Build environment mode for Kitchen. Options are ["+cookModeFlagEnum.Choices()+"].")
		fs.StringVar(
			&c.RepositoryURL,
			"repository",
			"",
			"URL of a git repository with the recipe to run. Must have a recipe configuration at infra/config/recipes.cfg. If unspecified will look for bundled recipes at -checkout-dir.")
		fs.StringVar(
			&c.Revision,
			"revision",
			"",
			"Revison of the recipe to run (if -repository is specified). It can be HEAD, a commit hash or a fully-qualified ref. (defaults to HEAD)")
		fs.StringVar(
			&c.rr.recipeName,
			"recipe",
			"",
			"Name of the recipe to run")
		fs.Var(
			&c.PythonPaths,
			"python-path",
			"Python path to include. Can be specified multiple times.")
		fs.StringVar(
			&c.CheckoutDir,
			"checkout-dir",
			"kitchen-checkout",
			"The directory to check out the repository to or to look for bundled recipes. It must either: not exist, be empty, be a valid Git repository, or be a recipe bundle.")
		fs.StringVar(
			&c.rr.workDir,
			"workdir",
			"kitchen-workdir",
			`The working directory for recipe execution. It must not exist or be empty. Defaults to "./kitchen-workdir."`)
		fs.StringVar(
			&c.Properties,
			"properties", "",
			"A JSON string containing the properties. Mutually exclusive with -properties-file.")
		fs.StringVar(
			&c.PropertiesFile,
			"properties-file", "",
			"A file containing a JSON string of properties. Mutually exclusive with -properties.")
		fs.StringVar(
			&c.rr.outputResultJSONFile,
			"output-result-json",
			"",
			"The file to write the JSON serialized returned value of the recipe to")
		fs.StringVar(
			&c.CacheDir,
			"cache-dir",
			"",
			"Directory with caches. If not empty, slashes will be converted to OS-native separators, "+
				"it will be made absolute and passed to the recipe.")
		fs.StringVar(
			&c.TempDir,
			"temp-dir",
			"",
			"Temporary directory to use. Forward slashes will be converted into OS-native separators.")

		// TODO(dnj, nodir): Remove deprecated flags.
		fs.BoolVar(
			&c.rr.opArgs.AnnotationFlags.EmitTimestamp,
			"timestamps",
			false,
			"If true, print CURRENT_TIMESTAMP annotations (DEPRECATED, use swarming mode).")
		fs.String(
			"recipe-engine-path",
			"",
			"(DEPRECATED, IGNORED) Path to a https://github.com/luci/recipes-py checkout")
		fs.Bool(
			"allow-gitiles",
			false,
			"(DEPRECATED, IGNORED) If true, kitchen will try to use Gitiles API to fetch a recipe.")

		c.logdog.addFlags(fs)

		return &c
	},
}

type cookRun struct {
	subcommands.CommandRunBase

	// For field documentation see the flags that these flags are bound to.

	RepositoryURL string
	Revision      string
	CheckoutDir   string

	Properties     string
	PropertiesFile string
	PythonPaths    stringlistflag.Flag
	CacheDir       string
	TempDir        string

	mode   cookModeFlag
	rr     recipeRun
	logdog cookLogDogParams
}

// normalizeFlags validates and normalizes flags.
func (c *cookRun) normalizeFlags(env environ.Env) error {
	if c.mode.cookMode == nil {
		return userError("missing mode (-mode)")
	}

	// Adjust some flags according to the chosen mode.
	if c.mode.onlyLogDog() {
		c.logdog.logDogOnly = true
	}
	c.rr.opArgs.AnnotationFlags.EmitTimestamp = c.mode.shouldEmitTimestamps() || c.rr.opArgs.AnnotationFlags.EmitTimestamp

	if c.rr.workDir == "" {
		return userError("-workdir is required")
	}

	if c.RepositoryURL != "" && c.Revision == "" {
		c.Revision = "HEAD"
	} else if c.RepositoryURL == "" && c.Revision != "" {
		return userError("if -repository is unspecified -revision must also be unspecified.")
	}

	if c.RepositoryURL != "" && !validRevisionRe.MatchString(c.Revision) {
		return fmt.Errorf("invalid revision %q", c.Revision)
	}

	if c.CheckoutDir == "" {
		return fmt.Errorf("empty -checkout-dir")
	}

	if c.rr.recipeName == "" {
		return userError("-recipe is required")
	}

	if c.Properties != "" && c.PropertiesFile != "" {
		return userError("only one of -properties or -properties-file is allowed")
	}

	// If LogDog is enabled, all required LogDog flags must be supplied.
	if err := c.logdog.setupAndValidate(c.mode.cookMode, env); err != nil {
		return err
	}

	// Normalize c.PythonPaths
	for i, p := range c.PythonPaths {
		p := filepath.FromSlash(p)
		p, err := filepath.Abs(p)
		if err != nil {
			return userError("invalid -python-path %q: %s", p, err)
		}
		c.PythonPaths[i] = p
	}

	c.TempDir = filepath.FromSlash(c.TempDir)

	return nil
}

// ensureAndRun ensures that we have recipes (according to -repository,
// -revision and -checkout-dir), and then runs them.
func (c *cookRun) ensureAndRun(ctx context.Context, env environ.Env) (recipeExitCode int, err error) {
	if c.RepositoryURL == "" {
		switch st, err := os.Stat(c.CheckoutDir); {
		case os.IsNotExist(err):
			return 0, userError("-repository not specified and -checkout-dir doesn't exist")
		case err != nil:
			return 0, errors.Annotate(err).Reason("could not stat -checkout-dir").Err()
		case !st.IsDir():
			return 0, userError("-checkout-dir is not a directory")
		}

		recipesPath, err := exec.LookPath(filepath.Join(c.CheckoutDir, "recipes"))
		if err != nil {
			return 0, errors.Annotate(err).Reason("could not find bundled recipes").Err()
		}
		c.rr.cmdPrefix = []string{recipesPath}
	} else {
		// Fetch the repo.
		if err := checkoutRepository(ctx, c.CheckoutDir, c.RepositoryURL, c.Revision); err != nil {
			return 0, errors.Annotate(err).Reason("could not checkout %(repo)q at %(rev)q to %(path)q").
				D("repo", c.RepositoryURL).
				D("rev", c.Revision).
				D("path", c.CheckoutDir).
				Err()
		}
		// Read the path to the recipes.py within the fetched repo.
		recipesPath, err := getRecipesPath(c.CheckoutDir)
		if err != nil {
			return 0, errors.Annotate(err).Reason("could not recipes.cfg").Err()
		}
		c.rr.cmdPrefix = []string{
			"python",
			filepath.Join(c.CheckoutDir, filepath.FromSlash(recipesPath), "recipes.py"),
		}
	}

	// Setup our working directory.
	c.rr.workDir, err = prepareRecipeRunWorkDir(c.rr.workDir)
	if err != nil {
		return 0, errors.Annotate(err).Reason("failed to prepare workdir").Err()
	}

	env.Set("PYTHONPATH", strings.Join(c.PythonPaths, string(os.PathListSeparator)))

	// Bootstrap through LogDog Butler?
	if c.logdog.active() {
		return c.runWithLogdogButler(ctx, &c.rr, env)
	}

	// This code is reachable only in buildbot mode.

	recipeCmd, err := c.rr.command(ctx, filepath.Join(c.TempDir, "rr"), env)
	if err != nil {
		return 0, fmt.Errorf("failed to build recipe command: %s", err)
	}
	printCommand(ctx, recipeCmd)

	recipeCmd.Stdout = os.Stdout
	recipeCmd.Stderr = os.Stderr

	err = recipeCmd.Run()
	if rv, has := exitcode.Get(err); has {
		return rv, nil
	}
	return 0, fmt.Errorf("failed to run recipe: %s", err)
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
		abs, err := filepath.Abs(native)
		if err != nil {
			return nil, userError("invalid -python-path %q: cannot make it absolute: %s", native, err)
		}
		props[p.name] = abs
	}

	return props, nil
}

// prepareProperties parses the properties specified by flags,
// validates them and add some extra properties to describe current build
// environment.
// May mutate some properties.
func (c *cookRun) prepareProperties(env environ.Env) (map[string]interface{}, error) {
	props, err := parseProperties(c.Properties, c.PropertiesFile)
	if err != nil {
		return nil, errors.Annotate(err).Reason("could not parse properties").Err()
	}
	if props == nil {
		props = map[string]interface{}{}
	}

	// Reject reserved properties.
	rejectProperties := []string{
		"$recipe_engine/path",
		"bot_id",
		// not specifying path_config means that all paths must be passed
		// explicitly. We do that below.
		"path_config",
	}
	for _, p := range rejectProperties {
		if _, ok := props[p]; ok {
			return nil, userError("%s property must not be set", p)
		}
	}

	// Configure paths that the recipe will use.
	pathProps, err := c.pathModuleProperties()
	if err != nil {
		return nil, err
	}
	props["$recipe_engine/path"] = pathProps

	// Use "generic" infra path config. See
	// https://chromium.googlesource.com/chromium/tools/depot_tools/+/master/recipes/recipe_modules/infra_paths/
	props["path_config"] = "generic"

	if err := c.mode.addProperties(props, env); err != nil {
		return nil, errors.Annotate(err).Reason("chosen mode could not add properties").Err()
	}
	if _, ok := props[PropertyBotId]; !ok {
		return nil, errors.Reason("chosen mode didn't add %(p)s property").
			D("p", PropertyBotId).
			Err()
	}

	err = migration.TransformProperties(props)
	if err != nil {
		return nil, err
	}

	return props, nil
}

func (c *cookRun) Run(a subcommands.Application, args []string, env subcommands.Env) (exitCode int) {
	ctx := cli.GetContext(a, c, env)
	sysEnv := environ.System()

	// Process flags.
	if len(args) != 0 {
		fmt.Fprintf(os.Stderr, "unexpected arguments: %v", args)
		return 1
	}
	if err := c.normalizeFlags(sysEnv); err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		fmt.Fprintln(os.Stderr, "for usage run: kitchen cook -help")
		return 1
	}

	rc, err := getReturnCode(c.runErr(ctx, args, sysEnv))
	switch {
	case errors.Unwrap(err) == context.Canceled:
		log.Warningf(ctx, "Process was cancelled.")
	case err != nil:
		if userError, ok := errors.Unwrap(err).(UserError); ok {
			fmt.Fprintln(os.Stderr, string(userError))
		} else {
			logAnnotatedErr(ctx, err)
		}
	}
	return rc
}

func (c *cookRun) runErr(ctx context.Context, args []string, env environ.Env) error {
	// initialize temp dir.
	if c.TempDir == "" {
		tdir, err := ioutil.TempDir("", "kitchen")
		if err != nil {
			return errors.Annotate(err).Reason("failed to create temporary directory").Err()
		}
		c.TempDir = tdir
		defer func() {
			if rmErr := os.RemoveAll(tdir); rmErr != nil {
				log.Warningf(ctx, "Failed to clean up temporary directory at [%s]: %s", tdir, rmErr)
			}
		}()
	}

	props, err := c.prepareProperties(env)
	if err != nil {
		return err
	}
	propsJSON, err := json.MarshalIndent(props, "", "  ")
	if err != nil {
		return errors.Annotate(err).Reason("could not marshal properties to JSON").Err()
	}
	log.Infof(ctx, "using properties:\n%s", propsJSON)

	// If we're not using LogDog, send out annotations.
	bootstrapSuccess := true
	if c.logdog.shouldEmitAnnotations() {
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

		for k, v := range props {
			// Order is not stable, but that is okay.
			jv, err := json.Marshal(v)
			if err != nil {
				return errors.Annotate(err).Err()
			}
			annotate("SET_BUILD_PROPERTY", k, string(jv))
		}
	}
	c.rr.properties = props

	// Run the recipe.
	recipeExitCode, err := c.ensureAndRun(ctx, env)
	if err != nil {
		bootstrapSuccess = false
		return err
	}
	return returnCodeError(recipeExitCode)
}

// unmarshalJSONWithNumber unmarshals JSON, where numbers are unmarshaled as
// json.Number.
func unmarshalJSONWithNumber(data []byte, dest interface{}) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	return decoder.Decode(dest)
}

func parseProperties(properties, propertiesFile string) (result map[string]interface{}, err error) {
	if properties != "" {
		err = unmarshalJSONWithNumber([]byte(properties), &result)
		if err != nil {
			err = userError("could not parse properties %s\n%s", properties, err)
		}
		return
	}
	if propertiesFile != "" {
		b, err := ioutil.ReadFile(propertiesFile)
		if err != nil {
			err = userError("could not read properties file %s\n%s", propertiesFile, err)
			return nil, err
		}
		err = unmarshalJSONWithNumber(b, &result)
		if err != nil {
			err = userError("could not parse JSON from file %s\n%s\n%s",
				propertiesFile, b, err)
		}
	}
	return
}

// printCommand prints cmd description to stdout and that it will be ran.
// panics if cannot read current directory or cannot make a command's current
// directory absolute.
func printCommand(ctx context.Context, cmd *exec.Cmd) {
	log.Infof(ctx, "running %q", cmd.Args)
	log.Infof(ctx, "command path: %s", cmd.Path)

	cd := cmd.Dir
	if cd == "" {
		var err error
		cd, err = os.Getwd()
		if err != nil {
			fmt.Fprintf(os.Stderr, "could not read working directory: %s\n", err)
			cd = ""
		}
	}
	if cd != "" {
		abs, err := filepath.Abs(cd)
		if err != nil {
			fmt.Fprintf(os.Stderr, "could not make path %q absolute: %s\n", cd, err)
		} else {
			log.Infof(ctx, "current directory: %s", abs)
		}
	}

	log.Infof(ctx, "env:\n%s", strings.Join(cmd.Env, "\n"))
}

// returnCodeError is a special error type that contains a process return code.
type returnCodeError int

func (err returnCodeError) Error() string { return fmt.Sprintf("return code: %d", err) }

// getReturnCode returns a return code value for a given error. It handles the
// returnCodeError type specially, returning its integer value verbatim.
//
// The error returned by getReturnCode is the same as the input error, unless
// the input error was a zero return code, in which case it will be nil.
func getReturnCode(err error) (int, error) {
	if err == nil {
		return 0, nil
	}
	if rc, ok := errors.Unwrap(err).(returnCodeError); ok {
		if rc == 0 {
			return 0, nil
		}
		return int(rc), err
	}
	return 1, err
}
