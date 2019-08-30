// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"flag"
	"strconv"

	"go.chromium.org/luci/common/flag/stringlistflag"
	"go.chromium.org/luci/logdog/client/butlerlib/streamproto"
	"go.chromium.org/luci/logdog/common/types"
)

const (
	defaultCheckoutDir = "kitchen-checkout"
)

// CookFlags are all of the flags necessary for the kitchen 'cook' command.
type CookFlags struct {
	// For field documentation see the flags that these flags are bound to.

	CheckoutDir string `json:"checkout_dir"`

	RecipeResultByteLimit int `json:"recipe_result_byte_limit"`

	Properties     PropertyFlag `json:"properties"`
	PropertiesFile string       `json:"properties_file"`
	CacheDir       string       `json:"cache_dir"`
	TempDir        string       `json:"temp_dir"`
	BuildURL       string       `json:"build_url"`

	OutputResultJSONPath string `json:"output_result_json"`

	RecipeName string `json:"recipe_name"`

	SystemAccount string `json:"system_account"`

	KnownGerritHost stringlistflag.Flag `json:"known_gerrit_host"`

	// Buildbucket flags.
	BuildbucketBuildID  int64  `json:"buildbucket_build_id"`
	BuildbucketHostname string `json:"buildbucket_hostname"`
	CallUpdateBuild     bool   `json:"call_update_build"`

	// LogDog flags.
	AnnotationURL    types.StreamAddr   `json:"annotation_url"`
	GlobalLogDogTags streamproto.TagMap `json:"global_tags"`
	NullOutput       bool               `json:"null_output"`
}

// Register the CookFlags with the provided FlagSet.
func (c *CookFlags) Register(fs *flag.FlagSet) {
	_ = fs.String("mode", "swarming", "deprecated, ignored")

	fs.StringVar(
		&c.RecipeName,
		"recipe",
		"",
		"Name of the recipe to run")

	fs.StringVar(
		&c.CheckoutDir,
		"checkout-dir",
		defaultCheckoutDir,
		"The directory where the recipes are checked out (via CIPD bundle). "+
			"Expected to contain a `recipes` and `recipes.bat` executable/script.")

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
	fs.String(
		"luci-system-account-json",
		"",
		"deprecated, ignored")

	fs.Var(
		&c.KnownGerritHost,
		"known-gerrit-host",
		"A hostname of a Gerrit host to force git authentication for. By default public "+
			"hosts are accessed anonymously, and the anonymous access has very low quota. Kitchen "+
			"needs to know all such hostnames in advance to be able to force authenticated access "+
			"to them.")
	fs.StringVar(
		&c.BuildbucketHostname,
		"buildbucket-hostname",
		"",
		"Hostname of the buildbucket for the current build.")
	fs.Int64Var(
		&c.BuildbucketBuildID,
		"buildbucket-build-id",
		0,
		"ID of the current buildbucket build.")
	fs.BoolVar(
		&c.CallUpdateBuild,
		"call-update-build",
		false,
		"Whether to call buildbucket.v2.Builds.UpdateBuild RPC "+
			"while build is running. "+
			"Requires -buildbucket-hostname, -buildbucket-build-id. ")

	fs.Var(
		&c.AnnotationURL,
		"logdog-annotation-url",
		"The URL of the LogDog annotation stream to use (logdog://host/project/prefix/+/name). The LogDog "+
			"project and prefix will be extracted from this URL.")
	fs.BoolVar(
		&c.NullOutput,
		"logdog-null-output",
		false,
		"If specified, dump all logdog data to null.")
	fs.Var(
		&c.GlobalLogDogTags,
		"logdog-tag",
		"Specify key[=value] tags to be applied to all log streams. Individual streams may override. Can "+
			"be specified multiple times.")
}

// Dump returns a []string command line argument which matches this CookFlags.
func (c *CookFlags) Dump() []string {
	ret := flagDumper{}

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

	ret.str("luci-system-account", c.SystemAccount)
	ret.list("known-gerrit-host", c.KnownGerritHost)
	ret.str("buildbucket-hostname", c.BuildbucketHostname)
	if c.BuildbucketBuildID != 0 {
		ret.str("buildbucket-build-id", strconv.FormatInt(c.BuildbucketBuildID, 10))
	}
	ret.boolean("call-update-build", c.CallUpdateBuild)

	if !c.AnnotationURL.IsZero() {
		ret = append(ret, "-logdog-annotation-url", c.AnnotationURL.String())
	}
	ret.stringMap("logdog-tag", c.GlobalLogDogTags)
	ret.boolean("logdog-null-output", c.NullOutput)

	return ret
}
