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
	"strconv"
	"strings"

	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"infra/tools/kitchen/proto"

	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/flag/stringlistflag"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/common/system/exitcode"
)

// BootstrapStepName is the name of kitchen's step where it makes preparations
// for running a recipe, e.g. fetches a repository.
const BootstrapStepName = "recipe bootstrap"

// cmdCook checks out a repository at a revision and runs a recipe.
var cmdCook = &subcommands.Command{
	UsageLine: "cook -repository <repository URL> -revision <revision> -recipe <recipe>",
	ShortDesc: "bootstraps a swarmbucket job.",
	LongDesc:  "Bootstraps a swarmbucket job.",
	CommandRun: func() subcommands.CommandRun {
		var c cookRun

		// Initialize our AnnotationFlags operational argument.
		c.rr.opArgs.AnnotationFlags = &recipe_engine.Arguments_AnnotationFlags{}

		fs := &c.Flags
		fs.Var(&c.mode,
			"mode",
			"Build environment mode for Kitchen. Options are ["+cookModeFlagEnum.Choices()+"].")
		fs.StringVar(
			&c.rr.recipeEnginePath,
			"recipe-engine-path",
			"",
			"Path to a https://github.com/luci/recipes-py checkout")
		fs.StringVar(&c.rr.repositoryURL, "repository", "", "URL of a git repository to fetch")
		fs.StringVar(
			&c.rr.revision,
			"revision",
			"HEAD",
			"Git commit hash to check out.")
		fs.StringVar(&c.rr.recipe, "recipe", "<recipe>", "Name of the recipe to run")
		fs.Var(&c.PythonPaths, "python-path", "Python path to include. Can be specified multiple times.")
		fs.StringVar(
			&c.rr.checkoutDir,
			"checkout-dir",
			"",
			"The directory to check out the repository to. "+
				"Defaults to ./<repo name>, where <repo name> is the last component of -repository.")
		fs.StringVar(
			&c.rr.workDir,
			"workdir",
			"",
			`The working directory for recipe execution. It must not exist or be empty. Defaults to "./kitchen-workdir."`)
		fs.StringVar(&c.Properties, "properties", "",
			"A json string containing the properties. Mutually exclusive with -properties-file.")
		fs.StringVar(&c.PropertiesFile, "properties-file", "",
			"A file containing a json string of properties. Mutually exclusive with -properties.")
		fs.StringVar(
			&c.rr.outputResultJSONFile,
			"output-result-json",
			"",
			"The file to write the JSON serialized returned value of the recipe to")
		fs.BoolVar(
			&c.rr.opArgs.AnnotationFlags.EmitTimestamp,
			"timestamps",
			false,
			"If true, print CURRENT_TIMESTAMP annotations.")
		fs.BoolVar(
			&c.rr.allowGitiles,
			"allow-gitiles",
			false,
			"If true, kitchen will try to use Gitiles API to fetch a recipe.")
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
			"Temporary directory. If not empty, slashes will be converted to OS-native separators, "+
				"it will be made absolute and passed to the recipe.")

		c.logdog.addFlags(fs)

		return &c
	},
}

type cookRun struct {
	subcommands.CommandRunBase

	Properties     string
	PropertiesFile string
	PythonPaths    stringlistflag.Flag
	CacheDir       string
	TempDir        string

	mode   cookModeFlag
	rr     recipeRemoteRun
	logdog cookLogDogParams
}

// normalizeFlags validates and normalizes flags.
func (c *cookRun) normalizeFlags(env environ.Env) error {
	if c.mode.cookMode == nil {
		return fmt.Errorf("missing mode (-mode)")
	}

	if err := c.rr.normalize(); err != nil {
		return err
	}

	if c.Properties != "" && c.PropertiesFile != "" {
		return fmt.Errorf("only one of -properties or -properties-file is allowed")
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
			return fmt.Errorf("invalid python path %q: %s", p, err)
		}
		c.PythonPaths[i] = p
	}

	return nil
}

// remoteRun runs `recipes.py remote` that checks out a repo, runs a recipe and
// returns exit code.
// Mutates env.
func (c *cookRun) remoteRun(ctx context.Context, tdir string, env environ.Env) (recipeExitCode int, err error) {
	// Setup our working directory.
	if err := c.rr.prepareWorkDir(); err != nil {
		return 0, errors.Annotate(err).Reason("failed to prepare workdir").Err()
	}

	env.Set("PYTHONPATH", strings.Join(c.PythonPaths, string(os.PathListSeparator)))

	// Bootstrap through LogDog Butler?
	if c.logdog.active() {
		return c.runWithLogdogButler(ctx, &c.rr, tdir, env)
	}

	recipeCmd, err := c.rr.command(ctx, tdir, env)
	if err != nil {
		return 0, fmt.Errorf("failed to build recipe command: %s", err)
	}
	printCommand(recipeCmd)

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
	paths := []struct{ name, path string }{
		{"cache_dir", c.CacheDir},
		{"temp_dir", c.TempDir},
	}
	props := make(map[string]string, len(paths))
	for _, p := range paths {
		if p.path == "" {
			continue
		}
		native := filepath.FromSlash(p.path)
		abs, err := filepath.Abs(native)
		if err != nil {
			return nil, errors.Annotate(err).Reason("could not make dir %(dir)s absolute").D("dir", native).Err()
		}
		props[p.name] = abs
	}

	return props, nil
}

// prepareProperties parses the properties specified by flags,
// validates them and add some extra properties to describe current build
// environment.
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
		if props[p] != "" {
			return nil, errors.Reason("%(p)s property must not be set").D("p", p).Err()
		}
	}

	// Configure paths that the recipe will use.
	if pathProps, err := c.pathModuleProperties();err != nil {
		return nil, err
	} else {
		props["$recipe_engine/path"] = pathProps
	}

	// Provide bot_id for the recipes.
	if botId, err := c.mode.botId(env); err != nil {
		return nil, err
	} else {
		props["bot_id"] = botId
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
		err = errors.Annotate(err).Reason("failed to normalize flags").Err()

		logAnnotatedErr(ctx, err)
		c.Flags.Usage()
		return 1
	}

	err := c.runErr(ctx, args, sysEnv)
	switch {
	case errors.Unwrap(err) == context.Canceled:
		log.Warningf(ctx, "Process was cancelled.")
	case err != nil:
		logAnnotatedErr(ctx, err)
	}
	return getReturnCode(err)
}

func (c *cookRun) runErr(ctx context.Context, args []string, env environ.Env) error {
	props, err := c.prepareProperties(env)
	if err != nil {
		return err
	}

	// If we're not using LogDog, send out annotations.
	bootstapSuccess := true
	emitTimestamps := c.rr.opArgs.AnnotationFlags.EmitTimestamp
	if c.logdog.shouldEmitAnnotations() {
		if emitTimestamps {
			annotateTime(ctx)
		}
		annotate("SEED_STEP", BootstrapStepName)
		annotate("STEP_CURSOR", BootstrapStepName)
		if emitTimestamps {
			annotateTime(ctx)
		}
		annotate("STEP_STARTED")
		defer func() {
			annotate("STEP_CURSOR", BootstrapStepName)
			if emitTimestamps {
				annotateTime(ctx)
			}
			if bootstapSuccess {
				annotate("STEP_CLOSED")
			} else {
				annotate("STEP_EXCEPTION")
			}
			if emitTimestamps {
				annotateTime(ctx)
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
	var recipeExitCode int
	err = withTempDir(ctx, func(ctx context.Context, tdir string) (err error) {
		recipeExitCode, err = c.remoteRun(ctx, tdir, env)
		return
	})
	if err != nil {
		bootstapSuccess = false
		return errors.Annotate(err).Err()
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
			err = fmt.Errorf("could not parse properties %s\n%s", properties, err)
		}
		return
	}
	if propertiesFile != "" {
		b, err := ioutil.ReadFile(propertiesFile)
		if err != nil {
			err = fmt.Errorf("could not read properties file %s\n%s", propertiesFile, err)
			return nil, err
		}
		err = unmarshalJSONWithNumber(b, &result)
		if err != nil {
			err = fmt.Errorf("could not parse JSON from file %s\n%s\n%s",
				propertiesFile, b, err)
		}
	}
	return
}

func annotateTime(ctx context.Context) {
	timestamp := clock.Get(ctx).Now().Unix()
	annotate("CURRENT_TIMESTAMP", strconv.FormatInt(timestamp, 10))
}

func annotate(args ...string) {
	fmt.Printf("@@@%s@@@\n", strings.Join(args, "@"))
}

// printCommand prints cmd description to stdout and that it will be ran.
// panics if cannot read current directory or cannot make a command's current
// directory absolute.
func printCommand(cmd *exec.Cmd) {
	fmt.Printf("running %q\n", cmd.Args)
	fmt.Printf("command path: %s\n", cmd.Path)

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
			fmt.Printf("current directory: %s\n", abs)
		}
	}

	fmt.Println("env:")
	for _, e := range cmd.Env {
		fmt.Printf("\t%s\n", e)
	}
}

// returnCodeError is a special error type that contains a process return code.
type returnCodeError int

func (err returnCodeError) Error() string { return fmt.Sprintf("return code: %d", err) }

// getReturnCode returns a return code value for a given error. It handles the
// returnCodeError type specially, returning its integer value verbatim.
func getReturnCode(err error) int {
	if err == nil {
		return 0
	}
	if rc, ok := errors.Unwrap(err).(returnCodeError); ok {
		return int(rc)
	}
	return 1
}
