// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"infra/tools/kitchen/cookflags"

	"github.com/luci/luci-go/client/archiver"
	swarming "github.com/luci/luci-go/common/api/swarming/swarming/v1"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/isolated"
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
					return errors.Annotate(err).Reason("combining isolateds").Err()
				}
				isoHash = string(newHash)
			}
			st.Properties.InputsRef.Isolated = isoHash
			// TODO(iannucci): add recipe_repository swarming tag
			// `led isolate` should be able to capture this and embed in the
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
