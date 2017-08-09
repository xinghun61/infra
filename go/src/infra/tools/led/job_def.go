// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"infra/tools/kitchen/cookflags"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
)

// JobDefinition defines a 'led' job. It's like a normal Swarming
// NewTaskRequest, but broken into two halves: Userland and Systemland.
//
// Userland
//
// Userland describes the sorts of things that are controlled by users of LUCI,
// i.e. in a buildbucket builder definition. These can be altered with the `led
// edit` and `led edit-recipe-bundle` subcommands. Applying changes to these
// 'permanently' in production will require a CL against the project repo
// configuration. This includes things like:
//   * The recipe source to use
//   * The recipe to run
//   * The recipe properties to pass
//   * The swarming dimensions to use
//
// Systemland
//
// Systemland describes the sorts of things that are controlled by the folks
// building and maintaining LUCI systems themselves, i.e. in the definition of
// the LUCI services themselves. These can be altered with the `led edit-system`
// subcommand. Applying changes to these 'permanently' in production will
// require a CL against LUCI's internal configuration. This includes things
// like:
//   * All other aspects of the swarming task definition, with special support
//     for:
//     * CIPD packages to install (including the version of kitchen).
//     * Environment variables for swarming to set when invoking kitchen.
//   * All other aspects of the kitchen cook command invocation.
type JobDefinition struct {
	// SwarmingHostname captures the swarming host to use for this job. It's set
	// on the initial `led get` command. This swarming host is also queried to
	// discover the default isolate host and namespace to use too (so,
	// effectively, this hostname implies the isolate host and namespace that the
	// rest of the led pipeline uses).
	SwarmingHostname string `json:"swarming_hostname"`

	// TODO(iannucci): maybe support other job invocations?

	// Userland describes the sorts of things that are controlled by users of
	// LUCI.
	U *Userland `json:"userland"`

	// Systemland describes the sorts of things that are controlled by the folks
	// building and maintaining LUCI systems themselves.
	S *Systemland `json:"systemland"`
}

// Userland is the data in a swarmbucket task which is controlled by the
// swarmbucket builder definition. All information here can be modified with the
// `edit` subcommand, and can be changed in production by changing the builder
// definitions.
type Userland struct {
	// Only one recipe source may be defined at a time. These are only use if the
	// Systemland's kitchen_args field is non-nil.
	//
	// If RecipeIsolatedHash is used, and the Systemland's swarming_task's
	// Properties.InputsRef.Isolated is set, the RecipeIsolatedHash will be
	// combined via isolated inclusions with the Properties.InputsRef.Isolated
	// when the job is launched with an `led launch` command.
	RecipeIsolatedHash string            `json:"recipe_isolated_hash"`
	RecipeProdSource   *RecipeProdSource `json:"recipe_prod_source"`

	RecipeName       string                 `json:"recipe_name"`
	RecipeProperties map[string]interface{} `json:"recipe_properties"`

	ChangeListURL string `json:"changelist_url"`

	Dimensions map[string]string `json:"dimensions"`
}

// RecipeProdSource instructs the JobDefinition to obtain its recipes from
// a production (i.e. published in a repo) location.
type RecipeProdSource struct {
	RepositoryURL string `json:"repository_url"`
	Revision      string `json:"revision"`
}

// Systemland is the data in a swarmbucket task which is controlled by the LUCI
// maintainers. All information here can be modified with the `edit-system`
// subcommand, and can be changed in production by altering the implementation
// details of swarmbucket and/or the particular swarmbucket deployments.
type Systemland struct {
	// If non-nil, this will override the swarming_task's Properties.Command field
	// with a `kitchen cook` invocation. If it is nil, the swarming_task's
	// Properties.Command field will be
	KitchenArgs *cookflags.CookFlags `json:"kitchen_args"`

	// This env is the one that swarming gives to kitchen. If you need an
	// environment variable to show up in the recipe we recommend passing a recipe
	// property and interpreting it inside the recipe instead. If that doesn't
	// work for you, please contact infra-dev@chromium.org.
	Env map[string]string `json:"env"`

	// This maps from subdir to package name template to version. Note that the
	// 'root' directory is represented by the subdir '.', not the empty string.
	CipdPkgs map[string]map[string]string `json:"cipd_packages"`

	// This is the swarming task template. Any changes in the other Systemland
	// or Userland attributes are applied on-top of this. Env and CipdPkgs in
	// Systemland will replace the relevant fields here entirely (there's no
	// reason to use the versions in the SwarmingRpcsNewTaskRequest).
	SwarmingTask *swarming.SwarmingRpcsNewTaskRequest `json:"swarming_task"`
}
