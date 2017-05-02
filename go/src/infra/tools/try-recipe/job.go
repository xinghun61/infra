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
	SwarmingTask *swarming.SwarmingRpcsNewTaskRequest `json:"swarming_task"`
}

func JobDefinitionFromNewTaskRequest(r *swarming.SwarmingRpcsNewTaskRequest) (*JobDefinition, error) {
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
