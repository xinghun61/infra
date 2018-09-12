// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"infra/tools/kitchen/cookflags"

	"go.chromium.org/luci/client/archiver"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/isolated"
)

const recipeCheckoutDir = "recipe-checkout-dir"

func (u *Userland) apply(ctx context.Context, arc *archiver.Archiver, args *cookflags.CookFlags, ts *swarming.SwarmingRpcsTaskSlice) (extraTags []string, err error) {
	props := ts.Properties
	props.Dimensions = exfiltrateMap(u.Dimensions)

	if args != nil {
		if u.RecipeIsolatedHash != "" {
			args.RepositoryURL = ""
			args.Revision = ""
			args.CheckoutDir = recipeCheckoutDir

			isoHash := u.RecipeIsolatedHash
			if props.InputsRef == nil {
				props.InputsRef = &swarming.SwarmingRpcsFilesRef{}
			}
			if props.InputsRef.Isolated != "" {
				toCombine := isolated.HexDigests{
					isolated.HexDigest(isoHash),
					isolated.HexDigest(props.InputsRef.Isolated),
				}
				newHash, err := combineIsolates(ctx, arc, toCombine...)
				if err != nil {
					return nil, errors.Annotate(err, "combining isolateds").Err()
				}
				isoHash = string(newHash)
			}
			props.InputsRef.Isolated = isoHash
			// TODO(iannucci): add recipe_repository swarming tag
			// `led isolate` should be able to capture this and embed in the
			// JobDefinition.
		} else if u.RecipeGitSource != nil {
			args.RepositoryURL = u.RecipeGitSource.RepositoryURL
			args.Revision = u.RecipeGitSource.Revision

			tagRevision := u.RecipeGitSource.Revision
			if tagRevision == "" {
				tagRevision = "HEAD"
			}
			extraTags = append(extraTags,
				"recipe_repository:"+u.RecipeGitSource.RepositoryURL,
				"recipe_revision:"+u.RecipeGitSource.Revision,
			)
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

	return extraTags, nil
}
