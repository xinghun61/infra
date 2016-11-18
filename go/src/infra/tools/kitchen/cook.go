// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/url"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/flag/stringlistflag"
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
		fs := &c.Flags
		fs.StringVar(
			&c.RecipeEnginePath,
			"recipe-engine-path",
			"",
			"Path to a https://github.com/luci/recipes-py checkout")
		fs.StringVar(&c.RepositoryURL, "repository", "", "URL of a git repository to fetch")
		fs.StringVar(
			&c.Revision,
			"revision",
			"HEAD",
			"Git commit hash to check out.")
		fs.StringVar(&c.Recipe, "recipe", "<recipe>", "Name of the recipe to run")
		fs.Var(&c.PythonPaths, "python-path", "Python path to include. Can be specified multiple times.")
		fs.StringVar(
			&c.CheckoutDir,
			"checkout-dir",
			"",
			"The directory to check out the repository to. "+
				"Defaults to ./<repo name>, where <repo name> is the last component of -repository.")
		fs.StringVar(
			&c.Workdir,
			"workdir",
			"",
			`The working directory for recipe execution. It must not exist or be empty. Defaults to "./kitchen-workdir."`)
		fs.StringVar(&c.Properties, "properties", "",
			"A json string containing the properties. Mutually exclusive with -properties-file.")
		fs.StringVar(&c.PropertiesFile, "properties-file", "",
			"A file containing a json string of properties. Mutually exclusive with -properties.")
		fs.StringVar(
			&c.OutputResultJSONFile,
			"output-result-json",
			"",
			"The file to write the JSON serialized returned value of the recipe to")
		fs.BoolVar(
			&c.Timestamps,
			"timestamps",
			false,
			"If true, print CURRENT_TIMESTAMP annotations.")
		fs.BoolVar(
			&c.AllowGitiles,
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

	// RecipeEnginePath is a path to a https://github.com/luci/recipes-py
	// checkout.
	// If present, `recipes.py remote` is used to fetch the recipe.
	// Required.
	RecipeEnginePath string
	AllowGitiles     bool

	RepositoryURL        string
	Revision             string
	Recipe               string
	CheckoutDir          string
	Workdir              string
	Properties           string
	PropertiesFile       string
	OutputResultJSONFile string
	Timestamps           bool
	PythonPaths          stringlistflag.Flag
	CacheDir             string
	TempDir              string

	logdog cookLogDogParams
}

// normalizeFlags validates and normalizes flags.
func (c *cookRun) normalizeFlags() error {
	if c.RecipeEnginePath == "" {
		return fmt.Errorf("-recipe-engine-path is required")
	}

	// Validate Repository.
	if c.RepositoryURL == "" {
		return fmt.Errorf("-repository is required")
	}
	repoURL, err := url.Parse(c.RepositoryURL)
	if err != nil {
		return fmt.Errorf("invalid repository %q: %s", repoURL, err)
	}

	repoName := path.Base(repoURL.Path)
	if repoName == "" {
		return fmt.Errorf("invalid repository %q: no path", repoURL)
	}

	// Validate Recipe.
	if c.Recipe == "" {
		return fmt.Errorf("-recipe is required")
	}

	if c.Properties != "" && c.PropertiesFile != "" {
		return fmt.Errorf("only one of -properties or -properties-file is allowed")
	}

	// If LogDog is enabled, all required LogDog flags must be supplied.
	if c.logdog.active() {
		if err := c.logdog.validate(); err != nil {
			return err
		}
	}

	// Fix CheckoutDir.
	if c.CheckoutDir == "" {
		c.CheckoutDir = repoName
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
func (c *cookRun) remoteRun(ctx context.Context, props map[string]interface{}) (recipeExitCode int, err error) {
	if c.RecipeEnginePath == "" {
		panic("recipe engine path is unspecified")
	}

	// Pass properties in a file.
	propertiesFile, err := ioutil.TempFile("", "")
	if err != nil {
		return 0, err
	}
	defer os.Remove(propertiesFile.Name())
	if err := json.NewEncoder(propertiesFile).Encode(props); err != nil {
		return 0, fmt.Errorf("could not write properties file: %s", err)
	}

	workDir := c.Workdir
	if workDir == "" {
		workDir = "kitchen-workdir"
	}
	if abs, err := filepath.Abs(workDir); err != nil {
		return 0, fmt.Errorf("could not make workdir %q absolute: %s", workDir, err)
	} else {
		workDir = abs
	}
	if err := prepareWorkdir(workDir); err != nil {
		return 0, err
	}

	cmdFunc := func(ctx context.Context, env environ.Env) (*exec.Cmd, error) {
		recipeCmd := exec.CommandContext(
			ctx,
			"python",
			filepath.Join(c.RecipeEnginePath, "recipes.py"),
			"remote",
			"--repository", c.RepositoryURL,
			"--revision", c.Revision,
			"--workdir", c.CheckoutDir, // this is not a workdir for recipe run!
		)
		recipeCmd.Env = env.Sorted()

		// remote subcommand does not sniff whether repository is gitiles or generic
		// git. Instead it accepts an explicit "--use-gitiles" flag.
		// We are not told whether the repo is gitiles or not, so sniff it here.
		if c.AllowGitiles && looksLikeGitiles(c.RepositoryURL) {
			recipeCmd.Args = append(recipeCmd.Args, "--use-gitiles")
		}

		// Now add the arguments for the recipes.py that will be fetched.
		recipeCmd.Args = append(recipeCmd.Args,
			"--",
			"run",
			"--properties-file", propertiesFile.Name(),
			"--workdir", workDir,
			"--output-result-json", c.OutputResultJSONFile,
		)
		if c.Timestamps {
			recipeCmd.Args = append(recipeCmd.Args, "--timestamps")
		}
		recipeCmd.Args = append(recipeCmd.Args, c.Recipe)
		return recipeCmd, nil
	}

	// Build our environment.
	env := environ.System()
	env.Set("PYTHONPATH", strings.Join(c.PythonPaths, string(os.PathListSeparator)))

	// Bootstrap through LogDog Butler?
	if c.logdog.active() {
		return c.runWithLogdogButler(ctx, cmdFunc, env)
	}

	recipeCmd, err := cmdFunc(ctx, env)
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
	prepare := func(p string) (string, error) {
		p = filepath.FromSlash(p)
		var err error
		p, err = filepath.Abs(p)
		if err != nil {
			return "", fmt.Errorf("could not make cache dir absolute: %s", err)
		}
		return p, nil
	}

	props := map[string]string{}
	if p, err := prepare(c.CacheDir); err != nil {
		return nil, err
	} else {
		props["cache_dir"] = p
	}

	if p, err := prepare(c.TempDir); err != nil {
		return nil, err
	} else {
		props["temp_dir"] = p
	}

	return props, nil
}

func (c *cookRun) Run(a subcommands.Application, args []string) (exitCode int) {
	ctx := cli.GetContext(a, c)

	// Process flags.
	var err error
	if len(args) != 0 {
		err = fmt.Errorf("unexpected arguments %v\n", args)
	} else {
		err = c.normalizeFlags()
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		c.Flags.Usage()
		return 1
	}

	// Parse properties.
	props, err := parseProperties(c.Properties, c.PropertiesFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "could not parse properties: %s", err)
		return 1
	}

	// Let infra_path recipe module know that we are using swarmbucket paths.
	// Relevant code:
	// https://chromium.googlesource.com/chromium/tools/depot_tools/+/248331450c05c59c8e966c806f00bd2475e36603/recipe_modules/infra_paths/api.py#12
	// https://chromium.googlesource.com/chromium/tools/depot_tools/+/248331450c05c59c8e966c806f00bd2475e36603/recipe_modules/infra_paths/path_config.py#57
	if _, ok := props["path_config"]; ok {
		fmt.Fprintln(os.Stderr, `"path_config" property must not be set; it is reserved by kitchen`)
	}
	if props == nil {
		props = map[string]interface{}{}
	}
	// Configure paths that the recipe will use.
	if pathProps, err := c.pathModuleProperties(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	} else if len(pathProps) > 0 {
		props["$recipe_engine/path"] = pathProps
	}

	// If we're not using LogDog, send out annotations.
	bootstapSuccess := true
	if c.logdog.emitAnnotations() {
		if c.Timestamps {
			annotateTime(ctx)
		}
		annotate("SEED_STEP", BootstrapStepName)
		annotate("STEP_CURSOR", BootstrapStepName)
		if c.Timestamps {
			annotateTime(ctx)
		}
		annotate("STEP_STARTED")
		defer func() {
			annotate("STEP_CURSOR", BootstrapStepName)
			if c.Timestamps {
				annotateTime(ctx)
			}
			if bootstapSuccess {
				annotate("STEP_CLOSED")
			} else {
				annotate("STEP_EXCEPTION")
			}
			if c.Timestamps {
				annotateTime(ctx)
			}
		}()

		for k, v := range props {
			// Order is not stable, but that is okay.
			jv, err := json.Marshal(v)
			if err != nil {
				fmt.Fprintln(os.Stderr, err)
				return 1
			}
			annotate("SET_BUILD_PROPERTY", k, string(jv))
		}
	}

	// Run the recipe.
	recipeExitCode, err := c.remoteRun(ctx, props)
	if err != nil {
		bootstapSuccess = false
		if err != context.Canceled {
			fmt.Fprintln(os.Stderr, err)
		}
		return -1
	}
	return recipeExitCode
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

func looksLikeGitiles(rawurl string) bool {
	u, err := url.Parse(rawurl)
	return err == nil && strings.HasSuffix(u.Host, ".googlesource.com")
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

func prepareWorkdir(workDir string) error {
	switch entries, err := ioutil.ReadDir(workDir); {
	case os.IsNotExist(err):
		return os.Mkdir(workDir, 0777)

	case err != nil:
		return fmt.Errorf("could not read workdir %q: %s", workDir, err)

	case len(entries) > 0:
		return fmt.Errorf("workdir %q is not empty", workDir)

	default:
		return nil
	}
}
