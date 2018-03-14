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
					return errors.Annotate(err, "combining isolateds").Err()
				}
				isoHash = string(newHash)
			}
			st.Properties.InputsRef.Isolated = isoHash
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
			st.Tags = append(st.Tags,
				"recipe_repository:"+u.RecipeGitSource.RepositoryURL,
				"recipe_revision:"+u.RecipeGitSource.Revision,
			)
		} else if u.RecipeCIPDSource != nil {
			if st.Properties == nil {
				st.Properties = &swarming.SwarmingRpcsTaskProperties{}
			}
			if st.Properties.CipdInput == nil {
				st.Properties.CipdInput = &swarming.SwarmingRpcsCipdInput{}
			}
			st.Properties.CipdInput.Packages = append(
				st.Properties.CipdInput.Packages, &swarming.SwarmingRpcsCipdPackage{
					Path:        args.CheckoutDir,
					PackageName: u.RecipeCIPDSource.Package,
					Version:     u.RecipeCIPDSource.Version,
				})
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
