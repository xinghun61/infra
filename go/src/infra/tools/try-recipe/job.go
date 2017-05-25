// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/hex"
	"encoding/json"
	"flag"
	"regexp"
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

// RecipeProdSource represents the configuration for recipes which have been
// committed to a repo.
type RecipeProdSource struct {
	RepositoryURL string `json:"repository_url"`
	Revision      string `json:"revision"`
}

// Userland is the data in a swarmbucket task which is kitchen "down". All
// information here can be modified with the `edit` subcommand, and can be
// changed in production by changing the builder definitions.
type Userland struct {
	// Only one source may be defined at a time.
	RecipeIsolatedHash string            `json:"recipe_isolated_hash"`
	RecipeProdSource   *RecipeProdSource `json:"recipe_prod_source"`

	RecipeName       string                 `json:"recipe_name"`
	RecipeProperties map[string]interface{} `json:"recipe_properties"`

	Dimensions map[string]string `json:"dimensions"`
}

func (u *Userland) apply(ctx context.Context, arc *archiver.Archiver, args *cookflags.CookFlags, st *swarming.SwarmingRpcsNewTaskRequest) error {
	st.Properties.Dimensions = exfiltrateMap(u.Dimensions)

	if args != nil {
		if u.RecipeIsolatedHash != "" {
			args.RepositoryURL = ""
			args.Revision = ""
			args.CheckoutDir = recipeCheckoutDir

			isoHash := u.RecipeIsolatedHash
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
					return errors.Annotate(err).Reason("combining isolateds").Err()
				}
				isoHash = string(newHash)
			}
			st.Properties.InputsRef.Isolated = isoHash
			// TODO(iannucci): add recipe_repository swarming tag
			// `try-recipe isolate` should be able to capture this and embed in the
			// JobDefinition.
		} else if u.RecipeProdSource != nil {
			args.RepositoryURL = u.RecipeProdSource.RepositoryURL
			args.Revision = u.RecipeProdSource.Revision

			tagRevision := u.RecipeProdSource.Revision
			if tagRevision == "" {
				tagRevision = "HEAD"
			}
			st.Tags = append(st.Tags,
				"recipe_repository:"+u.RecipeProdSource.RepositoryURL,
				"recipe_revision:"+u.RecipeProdSource.Revision,
			)
		}

		if u.RecipeName != "" {
			args.RecipeName = u.RecipeName
			st.Tags = append(st.Tags, "recipe_name:"+u.RecipeName)
		}

		if u.RecipeProperties != nil {
			args.Properties = u.RecipeProperties
			args.PropertiesFile = ""
		}
	}

	return nil
}

// Systemland is the data in a swarmbucket task which is kitchen "up". All
// information here can be modified with the `edit-system` subcommand, and can
// be changed in production by altering the implementation details of
// swarmbucket and/or the particular swarmbucket deployments.
type Systemland struct {
	KitchenArgs *cookflags.CookFlags `json:"kitchen_args"`

	// This env is the one that swarming gives to kitchen. If we need
	// a userspace-env we should add the relevent options to Kitchen so it can
	// present a modified environment to the task, but not be influced by it
	// directly.
	Env map[string]string `json:"env"`

	CipdPkgs map[string]map[string]string `json:"cipd_packages"`

	SwarmingTask *swarming.SwarmingRpcsNewTaskRequest `json:"swarming_task"`
}

func (s *Systemland) genSwarmingTask(ctx context.Context, uid string) (st *swarming.SwarmingRpcsNewTaskRequest, args *cookflags.CookFlags, err error) {
	st = &(*s.SwarmingTask)
	st.Properties = &(*st.Properties)
	st.Properties.Env = exfiltrateMap(s.Env)

	if s.KitchenArgs != nil {
		args = &(*s.KitchenArgs)

		// generate AnnotationURL, if needed, and add it to tags
		if strings.Contains(string(args.LogDogFlags.AnnotationURL.Path), generateLogdogToken) {
			var prefix logdog_types.StreamName
			prefix, err = generateLogdogStream(ctx, uid)
			if err != nil {
				err = errors.Annotate(err).Reason("generating logdog prefix").Err()
				return
			}
			args.LogDogFlags.AnnotationURL.Path = logdog_types.StreamPath(strings.Replace(
				string(args.LogDogFlags.AnnotationURL.Path), generateLogdogToken,
				string(prefix), -1))
		}
		if !args.LogDogFlags.AnnotationURL.IsZero() {
			st.Tags = append(st.Tags, "log_location:"+args.LogDogFlags.AnnotationURL.String())
		}
	}

	return
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

	// TODO(iannucci): maybe support other job invocations?

	U *Userland   `json:"userland"`
	S *Systemland `json:"systemland"`
}

func trimTags(tags []string, trimPrefixes []string) []string {
	quoted := make([]string, len(trimPrefixes))
	for i, p := range trimPrefixes {
		quoted[i] = regexp.QuoteMeta(p)
	}
	re := regexp.MustCompile("(" + strings.Join(quoted, ")|(") + ")")
	newTags := make([]string, 0, len(tags))
	for _, t := range newTags {
		if !re.MatchString(t) {
			newTags = append(newTags, t)
		}
	}
	return newTags
}

// JobDefinitionFromNewTaskRequest generates a new JobDefinition by parsing the
// given SwarmingRpcsNewTaskRequest. It expects that the
// SwarmingRpcsNewTaskRequest is for a swarmbucket-originating job (or at least
// looks like one :)).
func JobDefinitionFromNewTaskRequest(r *swarming.SwarmingRpcsNewTaskRequest) (*JobDefinition, error) {
	ret := &JobDefinition{
		S: &Systemland{SwarmingTask: r, KitchenArgs: &cookflags.CookFlags{}},
		U: &Userland{},
	}

	ingestMap := func(pairs *[]*swarming.SwarmingRpcsStringPair) map[string]string {
		ret := make(map[string]string, len(*pairs))
		for _, p := range *pairs {
			ret[p.Key] = p.Value
		}
		*pairs = nil
		return ret
	}

	ret.S.Env = ingestMap(&r.Properties.Env)
	ret.S.CipdPkgs = map[string]map[string]string{}
	for _, pkg := range r.Properties.CipdInput.Packages {
		if _, ok := ret.S.CipdPkgs[pkg.Path]; !ok {
			ret.S.CipdPkgs[pkg.Path] = map[string]string{}
		}
		ret.S.CipdPkgs[pkg.Path][pkg.PackageName] = pkg.Version
	}
	r.Properties.CipdInput.Packages = nil
	if r.Properties.CipdInput.Server == "" && r.Properties.CipdInput.ClientPackage == nil {
		r.Properties.CipdInput = nil
	}

	ret.U.Dimensions = ingestMap(&r.Properties.Dimensions)

	if len(r.Properties.Command) > 2 {
		if r.Properties.Command[0] == "kitchen${EXECUTABLE_SUFFIX}" && r.Properties.Command[1] == "cook" {
			fs := flag.NewFlagSet("kitchen_cook", flag.ContinueOnError)
			ret.S.KitchenArgs.Register(fs)
			if err := fs.Parse(r.Properties.Command[2:]); err != nil {
				return nil, errors.Annotate(err).Reason("parsing kitchen cook args").Err()
			}
			ret.S.SwarmingTask.Properties.Command = nil
			if !ret.S.KitchenArgs.LogDogFlags.AnnotationURL.IsZero() {
				// annotation urls are one-time use; if we got one as part of the new
				// task request, the odds are that it's already been used. We do this
				// replacement here so that when we launch the task we can generate
				// a unique annotation url.
				prefix, path := ret.S.KitchenArgs.LogDogFlags.AnnotationURL.Path.Split()
				prefix = generateLogdogToken
				ret.S.KitchenArgs.LogDogFlags.AnnotationURL.Path = prefix.AsPathPrefix(path)

				ret.S.SwarmingTask.Tags = trimTags(ret.S.SwarmingTask.Tags, []string{
					// this are all captured in KitchenArgs
					"log_location:",
					"recipe_name:",
					"recipe_repository:",
					"recipe_revision:",
				})

				if ret.S.KitchenArgs.RepositoryURL != "" && ret.S.KitchenArgs.Revision != "" {
					ret.U.RecipeProdSource = &RecipeProdSource{
						ret.S.KitchenArgs.RepositoryURL,
						ret.S.KitchenArgs.Revision,
					}
					ret.S.KitchenArgs.RepositoryURL = ""
					ret.S.KitchenArgs.Revision = ""
				}

				ret.U.RecipeName = ret.S.KitchenArgs.RecipeName
				ret.S.KitchenArgs.RecipeName = ""

				ret.U.RecipeProperties = ret.S.KitchenArgs.Properties
				ret.S.KitchenArgs.Properties = nil
			}
		}
	}

	return ret, nil
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

// EditJobDefinition is a temporary type returned by JobDefinition.Edit. It
// holds a mutable JobDefinition and an error, allowing a series of Edit
// commands to be called while buffering the error (if any). Obtain the modified
// JobDefinition (or error) by calling Finalize.
type EditJobDefinition struct {
	jd  JobDefinition
	err error
}

// Edit returns a mutator wrapper which knows how to manipulate various aspects
// of the JobDefinition.
func (jd *JobDefinition) Edit() *EditJobDefinition {
	return &EditJobDefinition{*jd, nil}
}

// Finalize returns the mutated JobDefinition and/or error.
func (ejd *EditJobDefinition) Finalize() (*JobDefinition, error) {
	if ejd.err != nil {
		return nil, ejd.err
	}
	return &ejd.jd, nil
}

func (ejd *EditJobDefinition) tweak(fn func(jd *JobDefinition) error) {
	if ejd.err == nil {
		ejd.err = fn(&ejd.jd)
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

// SwarmingServer allows you to modify the current SwarmingServer used by this
// try-recipe pipeline. Note that the isolated server is derived from this, so
// if you're editing this value, do so before passing the JobDefinition through
// the `isolate` subcommand.
func (ejd *EditJobDefinition) SwarmingServer(host string) {
	if host == "" {
		return
	}
	ejd.tweak(func(jd *JobDefinition) error {
		jd.SwarmingServer = host
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
	// apply systemland stuff
	st, args, err := jd.S.genSwarmingTask(ctx, uid)
	if err != nil {
		return nil, errors.Annotate(err).Reason("applying Systemland").Err()
	}

	// apply anything from userland
	if err := jd.U.apply(ctx, arc, args, st); err != nil {
		return nil, errors.Annotate(err).Reason("applying Userland").Err()
	}

	if args != nil {
		// Regenerate the command line
		st.Properties.Command = append([]string{"kitchen${EXECUTABLE_SUFFIX}", "cook"},
			args.Dump()...)
	}

	if len(jd.S.CipdPkgs) > 0 {
		if st.Properties.CipdInput == nil {
			st.Properties.CipdInput = &swarming.SwarmingRpcsCipdInput{}
		}

		for subdir, pkgsVers := range jd.S.CipdPkgs {
			for pkg, ver := range pkgsVers {
				st.Properties.CipdInput.Packages = append(
					st.Properties.CipdInput.Packages,
					&swarming.SwarmingRpcsCipdPackage{
						Path:        subdir,
						PackageName: pkg,
						Version:     ver,
					})
			}
		}
	}

	return st, nil
}

func exfiltrateMap(m map[string]string) []*swarming.SwarmingRpcsStringPair {
	if len(m) == 0 {
		return nil
	}
	ret := make([]*swarming.SwarmingRpcsStringPair, 0, len(m))
	for k, v := range m {
		ret = append(ret, &swarming.SwarmingRpcsStringPair{Key: k, Value: v})
	}
	return ret
}
