// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"flag"
	"strconv"

	"go.chromium.org/luci/common/flag/stringlistflag"
	"go.chromium.org/luci/common/flag/stringmapflag"
)

const (
	defaultCheckoutDir = "kitchen-checkout"
	defaultWorkDir     = "kitchen-workdir"
)

// CookFlags are all of the flags necessary for the kitchen 'cook' command.
type CookFlags struct {
	// For field documentation see the flags that these flags are bound to.

	Mode CookMode `json:"mode"`

	RepositoryURL string `json:"repository_url"`
	Revision      string `json:"revision"`
	CheckoutDir   string `json:"checkout_dir"`

	RecipeResultByteLimit int `json:"recipe_result_byte_limit"`

	Properties     PropertyFlag        `json:"properties"`
	PropertiesFile string              `json:"properties_file"`
	PrefixPathENV  stringlistflag.Flag `json:"prefix_path_env"`
	SetEnvAbspath  stringmapflag.Value `json:"set_env_abspath"`
	CacheDir       string              `json:"cache_dir"`
	TempDir        string              `json:"temp_dir"`
	BuildURL       string              `json:"build_url"`

	OutputResultJSONPath string `json:"output_result_json"`

	RecipeName string `json:"recipe_name"`
	WorkDir    string `json:"work_dir"`

	SystemAccount     string `json:"system_account"`
	SystemAccountJSON string `json:"system_account_json"`

	LogDogFlags LogDogFlags `json:"logdog_flags"`
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
		defaultCheckoutDir,
		"The directory to check out the repository to or to look for bundled recipes. It must either: not exist, be empty, "+
			"be a valid Git repository, or be a recipe bundle.")

	fs.StringVar(
		&c.WorkDir,
		"workdir",
		defaultWorkDir,
		`The working directory for recipe execution. It must not exist or be empty. Defaults to "./kitchen-workdir."`)

	if c.Properties == nil {
		c.Properties = PropertyFlag{}
	}
	fs.Var(
		&c.Properties,
		"properties",
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

	fs.StringVar(
		&c.SystemAccount,
		"luci-system-account",
		"",
		"If present, use this LUCI context logical account for system-level operations. Will likely be 'system'.")
	fs.StringVar(
		&c.SystemAccountJSON,
		"luci-system-account-json",
		"",
		"Explicitly authenticate system operations using this service account JSON file.")

	c.LogDogFlags.register(fs)
}

// Dump returns a []string command line argument which matches this CookFlags.
func (c *CookFlags) Dump() []string {
	ret := flagDumper{}

	ret.str("mode", c.Mode.String())
	ret.strDefault("workdir", c.WorkDir, defaultWorkDir)
	ret.str("repository", c.RepositoryURL)
	ret.str("revision", c.Revision)
	ret.strDefault("checkout-dir", c.CheckoutDir, defaultCheckoutDir)
	ret.strDefault("recipe-result-byte-limit", strconv.Itoa(c.RecipeResultByteLimit), "0")
	if len(c.Properties) > 0 {
		ret.str("properties", c.Properties.String())
	}
	ret.str("properties-file", c.PropertiesFile)
	ret.str("cache-dir", c.CacheDir)
	ret.str("temp-dir", c.TempDir)
	ret.str("build-url", c.BuildURL)
	ret.str("output-result-json", c.OutputResultJSONPath)
	ret.str("recipe", c.RecipeName)

	ret.list("prefix-path-env", c.PrefixPathENV)
	ret.stringMap("set-env-abspath", c.SetEnvAbspath)
	ret.str("luci-system-account", c.SystemAccount)
	ret.str("luci-system-account-json", c.SystemAccountJSON)

	return append(ret, c.LogDogFlags.Dump()...)
}
