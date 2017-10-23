// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/client/authcli"
	"go.chromium.org/luci/common/auth"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
)

func editCrCLCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "edit-cr-cl URL_TO_CHANGELIST",
		ShortDesc: "sets Chromium CL-related properties on this JobDefinition (for experimenting with tryjob recipes)",
		LongDesc: `This allows you to edit a JobDefinition for some tryjob recipe
(e.g. chromium_tryjob), and associate a changelist with it, as if the recipe
was triggered via Gerrit or Rietveld.

Recognized URLs:
	https://<rietveld_host>/<issue>
	https://<rietveld_host>/<issue>/#ps<patchset>
	https://<gerrit_host>/c/<path/to/project>/+/<issue>/<patchset>
	https://<gerrit_host>/c/<path/to/project>/+/<issue>/<patchset>
	https://<gerrit_host>/c/<issue>
	https://<gerrit_host>/c/<issue>/<patchset>
	https://<gerrit_host>/#/c/<issue>
	https://<gerrit_host>/#/c/<issue>/<patchset>

This command is more "art" than "science", and knows about a lot of the
(sometimes strange) conventions of the current chromium recipes. If you're
developing a new try recipe and are considering how to add a patchset as input
to the recipe, we would recommend picking a single property (say, 'patch_url'),
and then using e.g.
  'led edit -p patch_url="https://just.a.regular/url/to/the/patch"'
To set the patchset.

Maybe one day we'll reform the chromium recipes to have this level of sanity,
but until that time, this subcommand will be the nexus of weirdness.`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdEditCl{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			return ret
		},
	}
}

type cmdEditCl struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	changelistURL string
}

func (c *cmdEditCl) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	if len(args) != 1 {
		err = errors.New("expected URL_TO_CHANGELIST")
		return
	}

	c.changelistURL = args[0]
	if _, err = parseCrChangeListURL(c.changelistURL); err != nil {
		err = errors.Annotate(err, "invalid URL_TO_CHANGESET").Err()
		return
	}

	return c.authFlags.Options()
}

func (c *cmdEditCl) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	authOpts, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s\n\n", err)
		c.GetFlags().Usage()
		return 1
	}

	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	authClient, err := authenticator.Client()
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	err = editMode(ctx, func(jd *JobDefinition) error {
		ejd := jd.Edit()
		ejd.ChromiumCL(ctx, authClient, c.changelistURL)
		return ejd.Finalize()
	})
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	return 0
}
