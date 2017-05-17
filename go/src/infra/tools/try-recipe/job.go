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

// RecipeIsolatedSource instructs the JobDefinition to obtain its recipe from an
// isolated recipe bundle.
type RecipeIsolatedSource struct {
	Isolated string `json:"isolated"`
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
	SwarmingServer string `json:"swarming_server"`

	// Only one source may be defined at a time.
	RecipeIsolatedSource *RecipeIsolatedSource `json:"recipe_isolated_source"`

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

type EditJobDefinition struct {
	jd  JobDefinition
	err error
}

func (jd *JobDefinition) Edit() *EditJobDefinition {
	return &EditJobDefinition{*jd, nil}
}

func (ejd *EditJobDefinition) Finalize() (*JobDefinition, error) {
	if ejd.err != nil {
		return nil, ejd.err
	}
	return &ejd.jd, nil
}

func (ejd *EditJobDefinition) tweak(fn func(*EditJobDefinition) error) {
	if ejd.err == nil {
		ejd.err = fn(ejd)
	}
}

func (ejd *EditJobDefinition) RecipeSource(isolated string) {
	if isolated == "" {
		return
	}
	ejd.tweak(func(ejd *EditJobDefinition) error {
		ejd.jd.RecipeIsolatedSource = &RecipeIsolatedSource{isolated}
		return nil
	})
}

// Dimensions edits the swarming dimensions.
func (ejd *EditJobDefinition) Dimensions(dims map[string]string) {
	if len(dims) == 0 {
		return
	}
	ejd.tweak(func(ejd *EditJobDefinition) error {
		updateMap(dims, &ejd.jd.SwarmingTask.Properties.Dimensions)
		return nil
	})
}

// Env edits the swarming environment variables (i.e. before kitchen).
func (ejd *EditJobDefinition) Env(env map[string]string) {
	if len(env) == 0 {
		return
	}
	ejd.tweak(func(ejd *EditJobDefinition) error {
		updateMap(env, &ejd.jd.SwarmingTask.Properties.Env)
		return nil
	})
}

// Properties edits the recipe properties.
func (ejd *EditJobDefinition) Properties(props map[string]string) {
	if len(props) == 0 {
		return
	}
	ejd.tweak(func(ejd *EditJobDefinition) error {
		for k, v := range props {
			if v == "" {
				delete(ejd.jd.RecipeProperties, v)
			} else {
				var obj interface{}
				if err := json.Unmarshal([]byte(v), &obj); err != nil {
					return err
				}
				ejd.jd.RecipeProperties[k] = obj
			}
		}
		return nil
	})
}

func (ejd *EditJobDefinition) SwarmingServer(host string) {
	if host == "" {
		return
	}
	ejd.tweak(func(ejd *EditJobDefinition) error {
		ejd.jd.SwarmingServer = host
		return nil
	})
}
