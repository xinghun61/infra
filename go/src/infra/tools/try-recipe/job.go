// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"strings"

	swarming "github.com/luci/luci-go/common/api/swarming/swarming/v1"
	"github.com/luci/luci-go/common/errors"
)

const recipePropertiesJSON = "$RECIPE_PROPERTIES_JSON"

type SwarmingTaskProperties struct {
	// Dimensions describe the type of machine that this task should run on.
	Dimensions []*swarming.SwarmingRpcsStringPair `json:"dimensions"`

	// These paramters adjust how long various phases of the task may run for.
	ExecutionTimeoutSecs int64 `json:"execution_timeout_secs"`
	GracePeriodSecs      int64 `json:"grace_period_secs"`
	IoTimeoutSecs        int64 `json:"io_timeout_secs"`

	// These describe the data (files) input that the task will have available
	// when it runs.
	CipdInput *swarming.SwarmingRpcsCipdInput    `json:"cipd_input"`
	InputsRef *swarming.SwarmingRpcsFilesRef     `json:"inputs_ref"`
	Caches    []*swarming.SwarmingRpcsCacheEntry `json:"caches"`

	// These describe the command to run.
	Env         []*swarming.SwarmingRpcsStringPair `json:"env"`
	Command     []string                           `json:"command"`
	SecretBytes string                             `json:"secret_bytes"`

	// This indicates that the task's result should be cached and that subsequent
	// issuances of the exact same inputs will not re-execute the task.
	// Additionally, if this is false, swarming will not implement transparent
	// retries for transient (BOT_DIED) failures.
	Idempotent bool `json:"idempotent"`
}

type NewTaskRequest struct {
	Name     string `json:"name"`
	Priority int64  `json:"priority,string"`

	ParentTaskID string `json:"parent_task_id"`

	User                string `json:"user"`
	ServiceAccountToken string `json:"service_account_token"`

	Tags []string `json:"tags"`

	ExpirationSecs int64 `json:"expiration_secs,string"`

	Properties SwarmingTaskProperties `json:"properties"`
}

// JobDefinition defines a 'try-recipe' job. It's like a normal Swarming
// NewTaskRequest, but with some recipe-specific extras.
//
// In particular, the RecipeIsolatedHash will be combined with the task's
// isolated (if any), by uploading a new isolated which 'includes' both.
//
// Additionally, RecipeProperties will replace any args in the swarming task's
// command which are the string $RECIPE_PROPERTIES_JSON.
type JobDefinition struct {
	RecipeIsolatedHash string `json:"recipe_isolated_hash"`

	RecipeProperties map[string]interface{} `json:"recipe_properties"`

	// TODO(iannucci):
	// this should really be a swarming.SwarmingRpcsNewTaskRequest, but the way
	// that buildbucket sends it is incompatible with the go endpoints generated
	// struct. Hooray...  *rollseyes*.
	SwarmingTask *NewTaskRequest `json:"swarming_task"`
}

func JobDefinitionFromNewTaskRequest(r *NewTaskRequest) (*JobDefinition, error) {
	ret := &JobDefinition{SwarmingTask: r}

	for i, arg := range r.Properties.Command {
		if arg == "-properties" {
			if i+1 >= len(r.Properties.Command) {
				return nil, errors.New(
					"-properties in task definition, but no following json property data")
			}

			raw := r.Properties.Command[i+1]
			r.Properties.Command[i+1] = recipePropertiesJSON
			ret.RecipeProperties = map[string]interface{}{}
			if err := json.NewDecoder(strings.NewReader(raw)).Decode(&ret.RecipeProperties); err != nil {
				return nil, errors.Annotate(err).Reason("decoding -properties JSON").Err()
			}
			break
		}
	}

	return ret, nil
}

func updateMap(updates map[string]string, slc *[]*swarming.SwarmingRpcsStringPair) {
	if len(updates) == 0 {
		return
	}

	newSlice := make([]*swarming.SwarmingRpcsStringPair, 0, len(*slc)+len(updates))
	for k, v := range updates {
		if v != "" {
			newSlice = append(newSlice, &swarming.SwarmingRpcsStringPair{
				Key: k, Value: v})
		}
	}
	for _, pair := range *slc {
		if _, ok := updates[pair.Key]; !ok {
			newSlice = append(newSlice, pair)
		}
	}

	*slc = newSlice
}

func (jd *JobDefinition) Edit(dims, props, env map[string]string, recipe string) (*JobDefinition, error) {
	if len(dims) == 0 && len(props) == 0 && len(env) == 0 && recipe == "" {
		return jd, nil
	}

	ret := *jd
	ret.SwarmingTask = &(*jd.SwarmingTask)

	if recipe != "" {
		ret.RecipeIsolatedHash = recipe
	}

	updateMap(dims, &ret.SwarmingTask.Properties.Dimensions)
	updateMap(env, &ret.SwarmingTask.Properties.Env)

	if len(props) > 0 {
		ret.RecipeProperties = make(map[string]interface{}, len(jd.RecipeProperties)+len(props))
		for k, v := range props {
			if v != "" {
				var obj interface{}
				if err := json.NewDecoder(strings.NewReader(v)).Decode(&obj); err != nil {
					return nil, err
				}
				ret.RecipeProperties[k] = obj
			}
		}
		for k, v := range jd.RecipeProperties {
			if new, ok := props[k]; ok && new == "" {
				continue
			}
			ret.RecipeProperties[k] = v
		}
	}

	return &ret, nil
}
