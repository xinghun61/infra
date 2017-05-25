// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/hex"
	"encoding/json"
	"flag"
	"strings"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/client/archiver"
	swarming "github.com/luci/luci-go/common/api/swarming/swarming/v1"
	"github.com/luci/luci-go/common/data/rand/cryptorand"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/isolated"
	logdog_types "github.com/luci/luci-go/logdog/common/types"

	"infra/tools/kitchen/cookflags"
)

const recipeCheckoutDir = "recipe-checkout-dir"
const generateLogdogToken = "TRY_RECIPE_GENERATE_LOGDOG_TOKEN"
const isolateServerStandin = "TRY_RECIPE_ISOLATE_SERVER"

// JobDefinition defines a 'try-recipe' job. It's like a normal Swarming
// NewTaskRequest, but with some recipe-specific extras.
//
// In particular, the RecipeIsolatedHash will be combined with the task's
// isolated (if any), by uploading a new isolated which 'includes' both.
//
// Additionally, RecipeProperties will replace any args in the swarming task's
// command which are the string $RECIPE_PROPERTIES_JSON.
type JobDefinition struct {
	// TODO(iannucci): Split this definition into 'user' and 'system' portions.
	SwarmingServer string `json:"swarming_server"`

	// TODO(iannucci): maybe support other job invocations?

	KitchenArgs *cookflags.CookFlags `json:"kitchen_args"`

	SwarmingTask *swarming.SwarmingRpcsNewTaskRequest `json:"swarming_task"`
}

func JobDefinitionFromNewTaskRequest(r *swarming.SwarmingRpcsNewTaskRequest) (*JobDefinition, error) {
	ret := &JobDefinition{SwarmingTask: r}

	if len(r.Properties.Command) > 2 {
		if r.Properties.Command[0] == "kitchen${EXECUTABLE_SUFFIX}" && r.Properties.Command[1] == "cook" {
			fs := flag.NewFlagSet("kitchen_cook", flag.ContinueOnError)
			ret.KitchenArgs = &cookflags.CookFlags{}
			ret.KitchenArgs.Register(fs)
			if err := fs.Parse(r.Properties.Command[2:]); err != nil {
				return nil, errors.Annotate(err).Reason("parsing kitchen cook args").Err()
			}
			ret.SwarmingTask.Properties.Command = nil
			if !ret.KitchenArgs.LogDogFlags.AnnotationURL.IsZero() {
				// annotation urls are one-time use; if we got one as part of the new
				// task request, the odds are that it's already been used. We do this
				// replacement here so that when we launch the task we can generate
				// a unique annotation url.
				prefix, path := ret.KitchenArgs.LogDogFlags.AnnotationURL.Path.Split()
				prefix = generateLogdogToken
				ret.KitchenArgs.LogDogFlags.AnnotationURL.Path = prefix.AsPathPrefix(path)

				newTags := make([]string, 0, len(r.Tags))
				for _, t := range newTags {
					if !strings.HasPrefix(t, "log_location:") {
						newTags = append(newTags, t)
					}
				}
				ret.SwarmingTask.Tags = newTags
			}
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

func (ejd *EditJobDefinition) tweak(fn func(*JobDefinition) error) {
	if ejd.err == nil {
		ejd.err = fn(&ejd.jd)
	}
}

func (ejd *EditJobDefinition) tweakKitchenArgs(fn func(*cookflags.CookFlags) error) {
	if ejd.err == nil {
		if ejd.jd.KitchenArgs == nil {
			ejd.err = errors.New("command not compatible with non-kitchen jobs")
		} else {
			ejd.err = fn(ejd.jd.KitchenArgs)
		}
	}
}

func (ejd *EditJobDefinition) Recipe(recipe string) {
	if recipe == "" {
		return
	}
	ejd.tweakKitchenArgs(func(cf *cookflags.CookFlags) error {
		cf.RecipeName = recipe
		return nil
	})
}

func (ejd *EditJobDefinition) RecipeSource(isolated, repo, revision string) {
	if isolated == "" && repo == "" && revision == "" {
		return
	}
	ejd.tweakKitchenArgs(func(cf *cookflags.CookFlags) error {
		if isolated != "" && (repo != "" || revision != "") {
			return errors.New("specify either isolated or (repo||revision), but not both")
		}
		if isolated != "" {
			cf.RepositoryURL = isolateServerStandin
			cf.Revision = isolated
		} else {
			cf.RepositoryURL = repo
			cf.Revision = revision
		}
		return nil
	})
}

// Dimensions edits the swarming dimensions.
func (ejd *EditJobDefinition) Dimensions(dims map[string]string) {
	if len(dims) == 0 {
		return
	}
	ejd.tweak(func(jd *JobDefinition) error {
		updateMap(dims, &jd.SwarmingTask.Properties.Dimensions)
		return nil
	})
}

// Env edits the swarming environment variables (i.e. before kitchen).
func (ejd *EditJobDefinition) Env(env map[string]string) {
	if len(env) == 0 {
		return
	}
	ejd.tweak(func(jd *JobDefinition) error {
		updateMap(env, &jd.SwarmingTask.Properties.Env)
		return nil
	})
}

// Properties edits the recipe properties.
func (ejd *EditJobDefinition) Properties(props map[string]string) {
	if len(props) == 0 {
		return
	}
	ejd.tweakKitchenArgs(func(cf *cookflags.CookFlags) error {
		for k, v := range props {
			if v == "" {
				delete(cf.Properties, v)
			} else {
				var obj interface{}
				if err := json.Unmarshal([]byte(v), &obj); err != nil {
					return err
				}
				cf.Properties[k] = obj
			}
		}
		return nil
	})
}

func updateCipdPks(updates map[string]string, slc *[]*swarming.SwarmingRpcsCipdPackage) {
	if len(updates) == 0 {
		return
	}
	newMap := map[string]map[string]string{}
	add := func(path, pkg, version string) {
		if _, ok := newMap[path]; !ok {
			newMap[path] = map[string]string{pkg: version}
		} else {
			newMap[path][pkg] = version
		}
	}
	split := func(pathPkg string) (path, pkg string) {
		toks := strings.SplitN(pathPkg, ":", 2)
		if len(toks) == 1 {
			return ".", pathPkg
		}
		return toks[0], toks[1]
	}

	newSlice := make([]*swarming.SwarmingRpcsCipdPackage, 0, len(*slc)+len(updates))
	for pathPkg, vers := range updates {
		path, pkg := split(pathPkg)
		if vers != "" {
			newSlice = append(newSlice, &swarming.SwarmingRpcsCipdPackage{
				Path: path, PackageName: pkg, Version: vers})
		} else {
			add(path, pkg, vers)
		}
	}
	for _, entry := range *slc {
		if _, ok := newMap[entry.Path]; !ok {
			newSlice = append(newSlice, entry)
		} else {
			if _, ok := newMap[entry.Path][entry.PackageName]; !ok {
				newSlice = append(newSlice, entry)
			}
		}
	}
	*slc = newSlice
}

func (ejd *EditJobDefinition) CipdPkgs(cipdPkgs map[string]string) {
	if len(cipdPkgs) == 0 {
		return
	}
	ejd.tweak(func(jd *JobDefinition) error {
		updateCipdPks(cipdPkgs, &jd.SwarmingTask.Properties.CipdInput.Packages)
		return nil
	})
}

func (ejd *EditJobDefinition) SwarmingServer(host string) {
	if host == "" {
		return
	}
	ejd.tweak(func(jd *JobDefinition) error {
		jd.SwarmingServer = host
		return nil
	})
}

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

func generateLogdogStream(ctx context.Context, uid string) (prefix logdog_types.StreamName, err error) {
	buf := make([]byte, 32)
	if _, err := cryptorand.Read(ctx, buf); err != nil {
		return "", errors.Annotate(err).Reason("generating random token").Err()
	}
	return logdog_types.MakeStreamName("", "try-recipe", uid, hex.EncodeToString(buf))
}

// GetSwarmingNewTask builds a usable SwarmingRpcsNewTaskRequest from the
// JobDefinition, incorporating all of the extra bits of the JobDefinition.
func (jd *JobDefinition) GetSwarmingNewTask(ctx context.Context, uid string, arc *archiver.Archiver, swarmingServer string) (*swarming.SwarmingRpcsNewTaskRequest, error) {
	st := *jd.SwarmingTask
	st.Properties = &(*st.Properties)

	if jd.KitchenArgs != nil {
		args := *jd.KitchenArgs
		if strings.Contains(string(args.LogDogFlags.AnnotationURL.Path), generateLogdogToken) {
			prefix, err := generateLogdogStream(ctx, uid)
			if err != nil {
				return nil, errors.Annotate(err).Reason("generating logdog prefix").Err()
			}
			args.LogDogFlags.AnnotationURL.Path = logdog_types.StreamPath(strings.Replace(
				string(args.LogDogFlags.AnnotationURL.Path), generateLogdogToken,
				string(prefix), -1))
			st.Tags = append(st.Tags, "log_location:"+args.LogDogFlags.AnnotationURL.String())
		}

		if args.RepositoryURL == isolateServerStandin {
			isoHash := args.Revision
			if st.Properties == nil {
				st.Properties = &swarming.SwarmingRpcsTaskProperties{}
			}
			if st.Properties.InputsRef == nil {
				st.Properties.InputsRef = &swarming.SwarmingRpcsFilesRef{}
			}
			if st.Properties.InputsRef.Isolated != "" {
				toCombine := isolated.HexDigests{
					isolated.HexDigest(isoHash),
					isolated.HexDigest(st.Properties.InputsRef.Isolated),
				}
				newHash, err := combineIsolates(ctx, arc, toCombine...)
				if err != nil {
					return nil, errors.Annotate(err).Reason("combining isolateds").Err()
				}
				isoHash = string(newHash)
			}
			st.Properties.InputsRef.Isolated = isoHash

			args.RepositoryURL = ""
			args.Revision = ""
			args.CheckoutDir = recipeCheckoutDir
		}

		st.Properties.Command = append([]string{"kitchen${EXECUTABLE_SUFFIX}", "cook"},
			args.Dump()...)
	}

	return &st, nil
}
