// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"infra/tools/kitchen/cookflags"
	"strings"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
	logdog_types "go.chromium.org/luci/logdog/common/types"
)

func (s *Systemland) apply(ctx context.Context, uid string, ts *swarming.SwarmingRpcsTaskSlice) (args *cookflags.CookFlags, extraTags []string, err error) {
	ts.Properties.Env = exfiltrateMap(s.Env)

	if s.KitchenArgs != nil {
		args = &(*s.KitchenArgs)

		// generate AnnotationURL, if needed, and add it to tags
		if strings.Contains(string(args.LogDogFlags.AnnotationURL.Path), generateLogdogToken) {
			var prefix logdog_types.StreamName
			prefix, err = generateLogdogStream(ctx, uid)
			if err != nil {
				err = errors.Annotate(err, "generating logdog prefix").Err()
				return
			}
			args.LogDogFlags.AnnotationURL.Path = logdog_types.StreamPath(strings.Replace(
				string(args.LogDogFlags.AnnotationURL.Path), generateLogdogToken,
				string(prefix), -1))
		}
		if !args.LogDogFlags.AnnotationURL.IsZero() {
			extraTags = append(extraTags,
				"allow_milo:1",
				"log_location:"+args.LogDogFlags.AnnotationURL.String(),
			)
		}
	}

	if len(s.CipdPkgs) > 0 {
		if ts.Properties.CipdInput == nil {
			ts.Properties.CipdInput = &swarming.SwarmingRpcsCipdInput{}
		}

		for subdir, pkgsVers := range s.CipdPkgs {
			for pkg, ver := range pkgsVers {
				ts.Properties.CipdInput.Packages = append(
					ts.Properties.CipdInput.Packages,
					&swarming.SwarmingRpcsCipdPackage{
						Path:        subdir,
						PackageName: pkg,
						Version:     ver,
					})
			}
		}
	}

	return
}
