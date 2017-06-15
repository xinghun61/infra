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

	"github.com/luci/luci-go/client/archiver"
	swarming "github.com/luci/luci-go/common/api/swarming/swarming/v1"
	"github.com/luci/luci-go/common/data/rand/cryptorand"
	"github.com/luci/luci-go/common/errors"
	logdog_types "github.com/luci/luci-go/logdog/common/types"

	"infra/tools/kitchen/cookflags"
)

const generateLogdogToken = "TRY_RECIPE_GENERATE_LOGDOG_TOKEN"
const ledJobNamePrefix = "led: "

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
					"allow_milo:", // implied by KitchenArgs.LogDogFlags.AnnotationURL
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

	// prepend the name by default. This can be removed by manually editing the
	// job definition before launching it.
	if !strings.HasPrefix(ret.S.SwarmingTask.Name, ledJobNamePrefix) {
		ret.S.SwarmingTask.Name = ledJobNamePrefix + ret.S.SwarmingTask.Name
	}

	return ret, nil
}

// GetSwarmingNewTask builds a usable SwarmingRpcsNewTaskRequest from the
// JobDefinition, incorporating all of the extra bits of the JobDefinition.
func (jd *JobDefinition) GetSwarmingNewTask(ctx context.Context, uid string, arc *archiver.Archiver) (*swarming.SwarmingRpcsNewTaskRequest, error) {
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
		return "", errors.Annotate(err).Reason("generating random token").Err()
	}
	return logdog_types.MakeStreamName("", "led", uid, hex.EncodeToString(buf))
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
