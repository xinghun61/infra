// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"infra/tools/kitchen/cookflags"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
)

const recipeCheckoutDir = "recipe-checkout-dir"

func (u *Userland) apply(ctx context.Context, args *cookflags.CookFlags, ts *swarming.SwarmingRpcsTaskSlice) (extraTags []string) {
	props := ts.Properties
	props.Dimensions = exfiltrateMap(u.Dimensions)

	if args != nil {
		if u.RecipeIsolatedHash != "" {
			args.CheckoutDir = recipeCheckoutDir
			if props.InputsRef == nil {
				props.InputsRef = &swarming.SwarmingRpcsFilesRef{}
			}
			props.InputsRef.Isolated = u.RecipeIsolatedHash
			// TODO(iannucci): add recipe_repository swarming tag
			// `led isolate` should be able to capture this and embed in the
			// JobDefinition.
		} else if u.RecipeCIPDSource != nil {
			if props.CipdInput == nil {
				props.CipdInput = &swarming.SwarmingRpcsCipdInput{}
			}
			props.CipdInput.Packages = append(
				props.CipdInput.Packages, &swarming.SwarmingRpcsCipdPackage{
					Path:        args.CheckoutDir,
					PackageName: u.RecipeCIPDSource.Package,
					Version:     u.RecipeCIPDSource.Version,
				})
			extraTags = append(extraTags, "recipe_package:"+u.RecipeCIPDSource.Package)
		}

		if u.RecipeName != "" {
			args.RecipeName = u.RecipeName
			extraTags = append(extraTags, "recipe_name:"+u.RecipeName)
		}

		if u.RecipeProperties != nil {
			args.Properties = u.RecipeProperties
			args.PropertiesFile = ""
		}
	}

	return extraTags
}
