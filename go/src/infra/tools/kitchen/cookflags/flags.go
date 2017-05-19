// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

//go:generate stringer -type CookMode

import (
	"flag"

	"github.com/luci/luci-go/common/flag/stringlistflag"
)

// CookFlags are all of the flags necessary for the kitchen 'cook' command.
type CookFlags struct {
	// For field documentation see the flags that these flags are bound to.

	Mode CookMode

	RepositoryURL string
	Revision      string
	CheckoutDir   string

	RecipeResultByteLimit int

	Properties     string
	PropertiesFile string
	PythonPaths    stringlistflag.Flag
	PrefixPathENV  stringlistflag.Flag
	SetEnvAbspath  stringlistflag.Flag
	CacheDir       string
	TempDir        string
	BuildURL       string

	OutputResultJSONPath string

	RecipeName string
	WorkDir    string

	LogDogFlags LogDogFlags
}

// Register the CookFlags with the provided FlagSet.
func (c *CookFlags) Register(fs *flag.FlagSet) {
	fs.Var(&c.Mode,
		"mode",
		"Build environment mode for Kitchen. Options are ["+cookModeFlagEnum.Choices()+"].")

	fs.StringVar(
		&c.RepositoryURL,
		"repository",
		"",
		"URL of a git repository with the recipe to run. Must have a recipe configuration at infra/config/recipes.cfg. "+
			"If unspecified will look for bundled recipes at -checkout-dir.")

	fs.StringVar(
		&c.Revision,
		"revision",
		"",
		"Revison of the recipe to run (if -repository is specified). It can be HEAD, a commit hash or a fully-qualified "+
			"ref. (defaults to HEAD)")

	fs.StringVar(
		&c.RecipeName,
		"recipe",
		"",
		"Name of the recipe to run")

	// TODO(dnj): Remove this flag once all usages have been eliminated.
	fs.Var(
		&c.PythonPaths,
		"python-path",
		"(Deprecated, use -pythonpath).")

	fs.Var(
		&c.PythonPaths,
		"pythonpath",
		"Python path to include. Can be specified multiple times.")

	fs.Var(
		&c.PrefixPathENV,
		"prefix-path-env",
		"Add this forward-slash-delimited filesystem path to the beginning of the PATH "+
			"environment. The path value will be made absolute relative to the current working directory. "+
			"Can be specified multiple times, in which case values will appear at the beginning "+
			"of PATH in the order that they are supplied. Elements specified here will be forcefully "+
			"prefixed to the PATH of step commands by the recipe engine.")

	fs.Var(
		&c.SetEnvAbspath,
		"set-env-abspath",
		"Accepts a KEY=PATH environment variable. PATH is a filesystem path that will be exported "+
			"to the environment as an absolute path.")

	fs.StringVar(
		&c.CheckoutDir,
		"checkout-dir",
		"kitchen-checkout",
		"The directory to check out the repository to or to look for bundled recipes. It must either: not exist, be empty, "+
			"be a valid Git repository, or be a recipe bundle.")

	fs.StringVar(
		&c.WorkDir,
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
		&c.OutputResultJSONPath,
		"output-result-json",
		"",
		"The file to write the result to as a JSONPB-formatted CookResult proto message")

	fs.IntVar(
		&c.RecipeResultByteLimit,
		"recipe-result-byte-limit",
		0,
		"If positive, a limit, in bytes, for the result file contents written by recipe engine")

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

	fs.StringVar(
		&c.BuildURL,
		"build-url",
		"",
		"An optional URL to the build, which can be used to link to the build in LogDog.")

	c.LogDogFlags.register(fs)
}
