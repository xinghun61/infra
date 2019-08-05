// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"strings"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"

	"infra/tools/kitchen/cookflags"
)

// EditJobDefinition is a temporary type returned by JobDefinition.Edit. It
// holds a mutable JobDefinition and an error, allowing a series of Edit
// commands to be called while buffering the error (if any). Obtain the modified
// JobDefinition (or error) by calling Finalize.
type EditJobDefinition struct {
	jd  *JobDefinition
	err error
}

// Edit returns a mutator wrapper which knows how to manipulate various aspects
// of the JobDefinition.
func (jd *JobDefinition) Edit() *EditJobDefinition {
	return &EditJobDefinition{jd, nil}
}

// Finalize returns the error (if any)
func (ejd *EditJobDefinition) Finalize() error {
	if ejd.err != nil {
		return ejd.err
	}
	return nil
}

func (ejd *EditJobDefinition) tweak(fn func(jd *JobDefinition) error) {
	if ejd.err == nil {
		ejd.err = fn(ejd.jd)
	}
}

func (ejd *EditJobDefinition) tweakUserland(fn func(*Userland) error) {
	if ejd.err == nil {
		for _, slice := range ejd.jd.Slices {
			ejd.err = fn(&slice.U)
			if ejd.err != nil {
				return
			}
		}
	}
}

func (ejd *EditJobDefinition) tweakSystemland(fn func(*Systemland) error) {
	if ejd.err == nil {
		for _, slice := range ejd.jd.Slices {
			ejd.err = fn(&slice.S)
			if ejd.err != nil {
				return
			}
		}
	}
}

func (ejd *EditJobDefinition) tweakKitchenArgs(fn func(*cookflags.CookFlags) error) {
	ejd.tweakSystemland(func(s *Systemland) error {
		if s.KitchenArgs == nil {
			return errors.New("command not compatible with non-kitchen jobs")
		}
		return fn(s.KitchenArgs)
	})
}

// Recipe modifies the recipe to run. This must be resolvable in the current
// recipe source.
func (ejd *EditJobDefinition) Recipe(recipe string) {
	if recipe == "" {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		u.RecipeName = recipe
		return nil
	})
}

// RecipeSource modifies the source for the recipes. This can either be an
// isolated hash (i.e. bundled recipes) or it can be a cipd pkg/version pair.
func (ejd *EditJobDefinition) RecipeSource(isolated, cipdPkg, cipdVer string) {
	if isolated == "" && cipdPkg == "" && cipdVer == "" {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		switch {
		case isolated != "":
			if cipdPkg != "" {
				return errors.New("specify either isolated or cipdPkg, but not both")
			}
			u.RecipeCIPDSource = nil
			u.RecipeIsolatedHash = isolated

		default:
			u.RecipeCIPDSource = &RecipeCIPDSource{cipdPkg, cipdVer}
			u.RecipeIsolatedHash = ""
		}

		return nil
	})
}

// EditIsolated replaces the non-recipe isolate in the TaskSlice.
func (ejd *EditJobDefinition) EditIsolated(isolated string, cmd []string, cwd string) {
	if isolated == "" {
		return
	}
	ejd.tweak(func(jd *JobDefinition) error {
		for _, slc := range jd.Slices {
			ir := slc.S.TaskSlice.Properties.InputsRef
			if ir == nil {
				ir = &swarming.SwarmingRpcsFilesRef{}
				slc.S.TaskSlice.Properties.InputsRef = ir
			}
			ir.Isolated = isolated
			if len(cmd) > 0 {
				p := slc.S.TaskSlice.Properties
				p.Command = cmd
				p.RelativeCwd = cwd
				if len(p.ExtraArgs) > 0 {
					p.Command = append(p.Command, p.ExtraArgs...)
					p.ExtraArgs = nil
				}
			}
		}
		return nil
	})
}

// Dimensions edits the swarming dimensions.
func (ejd *EditJobDefinition) Dimensions(dims map[string]string) {
	if len(dims) == 0 {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		if u.Dimensions == nil {
			u.Dimensions = dims
		} else {
			updateMap(u.Dimensions, dims)
		}
		return nil
	})
}

// Env edits the swarming environment variables (i.e. before kitchen).
func (ejd *EditJobDefinition) Env(env map[string]string) {
	if len(env) == 0 {
		return
	}
	ejd.tweakSystemland(func(s *Systemland) error {
		if s.Env == nil {
			s.Env = env
		} else {
			updateMap(s.Env, env)
		}
		return nil
	})
}

// Priority edits the swarming task priority.
func (ejd *EditJobDefinition) Priority(priority int64) {
	if priority < 0 {
		return
	}
	ejd.jd.TopLevel.Priority = priority
}

// Properties edits the recipe properties.
func (ejd *EditJobDefinition) Properties(props map[string]string, auto bool) {
	if len(props) == 0 {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		for k, v := range props {
			if v == "" {
				delete(u.RecipeProperties, k)
			} else {
				var obj interface{}
				if err := json.Unmarshal([]byte(v), &obj); err != nil {
					if !auto {
						return err
					}
					obj = v
				}
				u.RecipeProperties[k] = obj
			}
		}
		return nil
	})
}

// CipdPkgs allows you to edit the cipd packages. The mapping is in the form of:
//    subdir:name/of/package -> version
// If version is empty, this package will be removed (if it's present).
func (ejd *EditJobDefinition) CipdPkgs(cipdPkgs map[string]string) {
	if len(cipdPkgs) == 0 {
		return
	}
	ejd.tweakSystemland(func(s *Systemland) error {
		for subdirPkg, vers := range cipdPkgs {
			subdir := "."
			pkg := subdirPkg
			if toks := strings.SplitN(subdirPkg, ":", 2); len(toks) > 1 {
				subdir, pkg = toks[0], toks[1]
			}
			if vers == "" {
				if _, ok := s.CipdPkgs[subdir]; ok {
					delete(s.CipdPkgs[subdir], pkg)
				}
			} else {
				if _, ok := s.CipdPkgs[subdir]; !ok {
					s.CipdPkgs[subdir] = map[string]string{}
				}
				s.CipdPkgs[subdir][pkg] = vers
			}
		}
		return nil
	})
}

// SwarmingHostname allows you to modify the current SwarmingHostname used by this
// led pipeline. Note that the isolated server is derived from this, so
// if you're editing this value, do so before passing the JobDefinition through
// the `isolate` subcommand.
func (ejd *EditJobDefinition) SwarmingHostname(host string) {
	if host == "" {
		return
	}
	ejd.tweak(func(jd *JobDefinition) error {
		if err := validateHost(host); err != nil {
			return errors.Annotate(err, "SwarmingHostname").Err()
		}
		jd.SwarmingHostname = host
		return nil
	})
}

// Experimental allows you to conveniently modify the
// "$recipe_engine/runtime['is_experimental']" property.
func (ejd *EditJobDefinition) Experimental(trueOrFalse string) {
	if trueOrFalse == "" {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		// If this task doesn't actually have a recipe associated with it, bail out.
		// This can happen if you use `led` on a non-recipe task.
		if u.RecipeName == "" {
			return nil
		}

		key := "$recipe_engine/runtime"
		current, ok := u.RecipeProperties[key].(map[string]interface{})
		if !ok {
			current = map[string]interface{}{}
		}
		if trueOrFalse == "true" {
			current["is_experimental"] = true
		} else if trueOrFalse == "false" {
			current["is_experimental"] = false
		} else {
			return errors.Reason(
				"experimental can only be 'true' or 'false', got %q", trueOrFalse).Err()
		}
		u.RecipeProperties[key] = current
		return nil
	})
}

// PrefixPathEnv controls swarming's env_prefix mapping.
//
// Values prepended with '!' will remove them from the existing list of values
// (if present). Otherwise these values will be appended to the current list of
// path-prefix-envs.
func (ejd *EditJobDefinition) PrefixPathEnv(values []string) {
	if len(values) == 0 {
		return
	}
	ejd.tweakSystemland(func(s *Systemland) error {
		var newPath []string
		for _, pair := range s.TaskSlice.Properties.EnvPrefixes {
			if pair.Key == "PATH" {
				newPath = pair.Value
				break
			}
		}

		for _, v := range values {
			if strings.HasPrefix(v, "!") {
				var toCut []int
				for i, cur := range newPath {
					if cur == v[1:] {
						toCut = append(toCut, i)
					}
				}
				for _, i := range toCut {
					newPath = append(newPath[:i], newPath[i+1:]...)
				}
			} else {
				newPath = append(newPath, v)
			}
		}

		for _, pair := range s.TaskSlice.Properties.EnvPrefixes {
			if pair.Key == "PATH" {
				pair.Value = newPath
				return nil
			}
		}

		s.TaskSlice.Properties.EnvPrefixes = append(
			s.TaskSlice.Properties.EnvPrefixes,
			&swarming.SwarmingRpcsStringListPair{Key: "PATH", Value: newPath})

		return nil
	})
}

func updateMap(dest, updates map[string]string) {
	if len(updates) == 0 {
		return
	}

	for k, v := range updates {
		if v == "" {
			delete(dest, k)
		} else {
			dest[k] = v
		}
	}
}
