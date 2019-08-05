// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"infra/tools/kitchen/cookflags"
	"strings"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	logdog_types "go.chromium.org/luci/logdog/common/types"
)

func (s *Systemland) apply(ctx context.Context, uid string, logPrefix logdog_types.StreamName, ts *swarming.SwarmingRpcsTaskSlice) (args *cookflags.CookFlags, extraTags []string) {
	ts.Properties.Env = exfiltrateMap(s.Env)

	if s.KitchenArgs != nil {
		args = &(*s.KitchenArgs)

		// generate AnnotationURL, if needed, and add it to tags
		if strings.Contains(string(args.AnnotationURL.Path), generateLogdogToken) {
			args.AnnotationURL.Path = logdog_types.StreamPath(strings.Replace(
				string(args.AnnotationURL.Path), generateLogdogToken,
				string(logPrefix), -1))
		}
		if !args.AnnotationURL.IsZero() {
			extraTags = append(extraTags,
				"allow_milo:1",
				"log_location:"+args.AnnotationURL.String(),
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
