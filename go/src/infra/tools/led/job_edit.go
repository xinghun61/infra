// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"infra/tools/kitchen/cookflags"
	"strings"

	"github.com/luci/luci-go/common/errors"
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
		if ejd.jd.U == nil {
			ejd.jd.U = &Userland{}
		}
		ejd.err = fn(ejd.jd.U)
	}
}

func (ejd *EditJobDefinition) tweakSystemland(fn func(*Systemland) error) {
	if ejd.err == nil {
		if ejd.jd.S == nil {
			ejd.jd.S = &Systemland{}
		}
		ejd.err = fn(ejd.jd.S)
	}
}

func (ejd *EditJobDefinition) tweakKitchenArgs(fn func(*cookflags.CookFlags) error) {
	if ejd.err == nil {
		if ejd.jd.S.KitchenArgs == nil {
			ejd.err = errors.New("command not compatible with non-kitchen jobs")
		} else {
			ejd.err = fn(ejd.jd.S.KitchenArgs)
		}
	}
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
func (ejd *EditJobDefinition) RecipeSource(isolated, repo, revision string) {
	if isolated == "" && repo == "" && revision == "" {
		return
	}
	ejd.tweakUserland(func(u *Userland) error {
		if isolated != "" && (repo != "" || revision != "") {
			return errors.New("specify either isolated or (repo||revision), but not both")
		}
		if isolated != "" {
			u.RecipeIsolatedHash = isolated
			u.RecipeProdSource = nil
		} else {
			u.RecipeProdSource = &RecipeProdSource{repo, revision}
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
	ejd.tweakSystemland(func(s *Systemland) error {
		s.SwarmingTask.Priority = priority
		return nil
	})
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
			return errors.Annotate(err).Reason("SwarmingHostname").Err()
		}
		jd.SwarmingHostname = host
		return nil
	})
}

// PrefixPathEnv controls kitchen's -prefix-path-env commandline variables.
// Values prepended with '!' will remove them from the existing list of values
// (if present). Otherwise these values will be appended to the current list of
// path-prefix-envs.
func (ejd *EditJobDefinition) PrefixPathEnv(values []string) {
	if len(values) == 0 {
		return
	}
	ejd.tweakKitchenArgs(func(cf *cookflags.CookFlags) error {
		for _, v := range values {
			if strings.HasPrefix(v, "!") {
				var toCut []int
				for i, cur := range cf.PrefixPathENV {
					if cur == v[1:] {
						toCut = append(toCut, i)
					}
				}
				for _, i := range toCut {
					cf.PrefixPathENV = append(
						cf.PrefixPathENV[:i],
						cf.PrefixPathENV[i+1:]...)
				}
			} else {
				cf.PrefixPathENV = append(cf.PrefixPathENV, v)
			}
		}
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
