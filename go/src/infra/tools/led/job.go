// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/hex"
	"flag"
	"regexp"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/client/archiver"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/rand/cryptorand"
	"go.chromium.org/luci/common/errors"
	logdog_types "go.chromium.org/luci/logdog/common/types"

	"infra/tools/kitchen/cookflags"
)

const generateLogdogToken = "TRY_RECIPE_GENERATE_LOGDOG_TOKEN"
const ledJobNamePrefix = "led: "

// JobSliceFromTaskSlice returns a JobSlice parsed from a SwarmingRpcsTaskSlice.
func JobSliceFromTaskSlice(ts *swarming.SwarmingRpcsTaskSlice) (*JobSlice, error) {
	ingestMap := func(pairs *[]*swarming.SwarmingRpcsStringPair) map[string]string {
		ret := make(map[string]string, len(*pairs))
		for _, p := range *pairs {
			ret[p.Key] = p.Value
		}
		*pairs = nil
		return ret
	}

	ret := &JobSlice{}
	ret.S.TaskSlice = ts
	props := ts.Properties

	ret.S.Env = ingestMap(&props.Env)
	ret.S.CipdPkgs = map[string]map[string]string{}
	for _, pkg := range props.CipdInput.Packages {
		if _, ok := ret.S.CipdPkgs[pkg.Path]; !ok {
			ret.S.CipdPkgs[pkg.Path] = map[string]string{}
		}
		ret.S.CipdPkgs[pkg.Path][pkg.PackageName] = pkg.Version
	}
	props.CipdInput.Packages = nil
	if props.CipdInput.Server == "" && props.CipdInput.ClientPackage == nil {
		props.CipdInput = nil
	}

	ret.U.Dimensions = ingestMap(&props.Dimensions)

	if len(props.Command) > 2 {
		if props.Command[0] == "kitchen${EXECUTABLE_SUFFIX}" && props.Command[1] == "cook" {
			ret.S.KitchenArgs = &cookflags.CookFlags{}

			fs := flag.NewFlagSet("kitchen_cook", flag.ContinueOnError)
			ret.S.KitchenArgs.Register(fs)
			if err := fs.Parse(props.Command[2:]); err != nil {
				return nil, errors.Annotate(err, "parsing kitchen cook args").Err()
			}
			props.Command = nil
			if !ret.S.KitchenArgs.LogDogFlags.AnnotationURL.IsZero() {
				// annotation urls are one-time use; if we got one as part of the new
				// task request, the odds are that it's already been used. We do this
				// replacement here so that when we launch the task we can generate
				// a unique annotation url.
				prefix, path := ret.S.KitchenArgs.LogDogFlags.AnnotationURL.Path.Split()
				prefix = generateLogdogToken
				ret.S.KitchenArgs.LogDogFlags.AnnotationURL.Path = prefix.AsPathPrefix(path)

				if ret.S.KitchenArgs.RepositoryURL != "" && ret.S.KitchenArgs.Revision != "" {
					ret.U.RecipeGitSource = &RecipeGitSource{
						ret.S.KitchenArgs.RepositoryURL,
						ret.S.KitchenArgs.Revision,
					}
					ret.S.KitchenArgs.RepositoryURL = ""
					ret.S.KitchenArgs.Revision = ""
				} else if cipdRecipe, ok := ret.S.CipdPkgs[ret.S.KitchenArgs.CheckoutDir]; ok {
					pkgname, vers := "", ""
					for pkgname, vers = range cipdRecipe {
						break
					}
					delete(ret.S.CipdPkgs[ret.S.KitchenArgs.CheckoutDir], pkgname)
					ret.U.RecipeCIPDSource = &RecipeCIPDSource{pkgname, vers}
				} else if iso := props.InputsRef.Isolated; iso != "" {
					// TODO(iannucci): actually seperate recipe files from the isolated
					// instead of assuming the whole thing is recipes.
					ret.U.RecipeIsolatedHash = iso
					props.InputsRef.Isolated = ""
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

// JobDefinitionFromNewTaskRequest generates a new JobDefinition by parsing the
// given SwarmingRpcsNewTaskRequest. It expects that the
// SwarmingRpcsNewTaskRequest is for a swarmbucket-originating job (or at least
// looks like one :)).
func JobDefinitionFromNewTaskRequest(r *swarming.SwarmingRpcsNewTaskRequest) (*JobDefinition, error) {
	numSlices := len(r.TaskSlices)
	if numSlices == 0 {
		numSlices = 1
	}
	ret := &JobDefinition{
		TopLevel: &ToplevelFields{
			r.Name,
			r.Priority,
			r.ServiceAccount,
			r.Tags,
			r.User,
		},
		Slices: make([]*JobSlice, numSlices),
	}
	me := errors.NewLazyMultiError(numSlices)
	var err error
	if len(r.TaskSlices) > 0 {
		for i := range ret.Slices {
			ret.Slices[i], err = JobSliceFromTaskSlice(r.TaskSlices[i])
			me.Assign(i, err)
		}
	} else {
		ret.Slices[0], err = JobSliceFromTaskSlice(&swarming.SwarmingRpcsTaskSlice{
			ExpirationSecs: r.ExpirationSecs,
			Properties:     r.Properties,
		})
	}

	ret.TopLevel.Tags = trimTags(ret.TopLevel.Tags, []string{
		"luci_project:",
	})

	// prepend the name by default. This can be removed by manually editing the
	// job definition before launching it.
	if !strings.HasPrefix(ret.TopLevel.Name, ledJobNamePrefix) {
		ret.TopLevel.Name = ledJobNamePrefix + ret.TopLevel.Name
	}

	return ret, me.Get()
}

func (tl *ToplevelFields) apply(st *swarming.SwarmingRpcsNewTaskRequest) {
	st.Name = tl.Name
	st.Priority = tl.Priority
	st.ServiceAccount = tl.ServiceAccount
	st.Tags = append([]string{}, tl.Tags...)
	st.User = tl.User
}

func (js *JobSlice) gen(ctx context.Context, uid string, arc *archiver.Archiver) (ret *swarming.SwarmingRpcsTaskSlice, extraTags []string, err error) {
	ret = &swarming.SwarmingRpcsTaskSlice{
		Properties: &swarming.SwarmingRpcsTaskProperties{},
	}
	var userTags, systemTags []string
	args, systemTags, err := js.S.apply(ctx, uid, ret)
	if err == nil {
		userTags, err = js.U.apply(ctx, arc, args, ret)
	}
	if err == nil && args != nil {
		ret.Properties.Command = append([]string{"kitchen${EXECUTABLE_SUFFIX}", "cook"},
			args.Dump()...)
		extraTags = append(systemTags, userTags...)
	}
	return
}

// GetSwarmingNewTask builds a usable SwarmingRpcsNewTaskRequest from the
// JobDefinition, incorporating all of the extra bits of the JobDefinition.
func (jd *JobDefinition) GetSwarmingNewTask(ctx context.Context, uid string, arc *archiver.Archiver) (*swarming.SwarmingRpcsNewTaskRequest, error) {
	st := &swarming.SwarmingRpcsNewTaskRequest{}
	jd.TopLevel.apply(st)
	for i, s := range jd.Slices {
		slc, extraTags, err := s.gen(ctx, uid, arc)
		if err != nil {
			return nil, errors.Annotate(err, "generating TaskSlice %d", i).Err()
		}
		// HACK(iannucci): Technically the swarming task could define task slice
		// fallbacks which had e.g. different logdog URLs or different recipe
		// versions. In practice, with buildbucket/kitchen, we don't do this, so the
		// `firstSliceTags` thing should be fine.
		if i == 0 {
			st.Tags = append(st.Tags, extraTags...)
		}
		st.TaskSlices = append(st.TaskSlices, slc)
	}
	return st, nil
}

// Private stuff

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

func generateLogdogStream(ctx context.Context, uid string) (prefix logdog_types.StreamName, err error) {
	buf := make([]byte, 32)
	if _, err := cryptorand.Read(ctx, buf); err != nil {
		return "", errors.Annotate(err, "generating random token").Err()
	}
	return logdog_types.MakeStreamName("", "led", uid, hex.EncodeToString(buf))
}

func trimTags(tags []string, keepPrefixes []string) []string {
	quoted := make([]string, len(keepPrefixes))
	for i, p := range keepPrefixes {
		quoted[i] = regexp.QuoteMeta(p)
	}
	re := regexp.MustCompile("(" + strings.Join(quoted, ")|(") + ")")
	newTags := make([]string, 0, len(tags))
	for _, t := range tags {
		if re.MatchString(t) {
			newTags = append(newTags, t)
		}
	}
	return newTags
}
