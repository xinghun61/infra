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
// isolated hash (i.e. bundled recipes) or it can be a repo/revision pair (i.e.
// production or gerrit CL recipes).
func (ejd *EditJobDefinition) RecipeSource(isolated, repo, revision, cipdPkg, cipdVer string) {
	if isolated == "" && repo == "" && revision == "" && cipdPkg == "" && cipdVer == "" {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		switch {
		case isolated != "":
			switch {
			case repo != "":
				return errors.New("specify either isolated or repo, but not both")
			case cipdPkg != "":
				return errors.New("specify either isolated or cipdPkg, but not both")
			}
			u.RecipeCIPDSource = nil
			u.RecipeGitSource = nil
			u.RecipeIsolatedHash = isolated

		case repo != "":
			if cipdPkg != "" {
				return errors.New("specify either repo or cipdPkg, but not both")
			}
			u.RecipeCIPDSource = nil
			u.RecipeGitSource = &RecipeGitSource{repo, revision}
			u.RecipeIsolatedHash = ""

		default:
			u.RecipeCIPDSource = &RecipeCIPDSource{cipdPkg, cipdVer}
			u.RecipeGitSource = nil
			u.RecipeIsolatedHash = ""
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
func (ejd *EditJobDefinition) Properties(props map[string]string) {
	if len(props) == 0 {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		for k, v := range props {
			if v == "" {
				delete(u.RecipeProperties, v)
			} else {
				var obj interface{}
				if err := json.Unmarshal([]byte(v), &obj); err != nil {
					return err
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
