// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
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
was triggered via Gerrit.

Recognized URLs:
	https://<gerrit_host>/c/<path/to/project>/+/<issue>/<patchset>
	https://<gerrit_host>/c/<path/to/project>/+/<issue>/<patchset>
	https://<gerrit_host>/c/<issue>
	https://<gerrit_host>/c/<issue>/<patchset>
	https://<gerrit_host>/#/c/<issue>
	https://<gerrit_host>/#/c/<issue>/<patchset>
	https://<googlesource_host>/<issue>

This command manipulates the property:
  $recipe_engine/buildbucket['build']['input']['gerritChanges'][atIndex]

For tasks consuming multiple input CLs, you can adjust which of the CLs you wish
to change by using the "-at-index" flag. By default this command modifies the
first CL on the task.
`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdEditCl{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.IntVar(&ret.atIndex, "at-index", 0,
				"For tasks taking multiple CLs; allows setting the CL at an index other than 0.")

			return ret
		},
	}
}

type cmdEditCl struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	changelistURL string
	atIndex       int
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
		return 2
	}

	err = editMode(ctx, func(jd *JobDefinition) error {
		ejd := jd.Edit()
		ejd.ChromiumCL(ctx, authClient, c.changelistURL, c.atIndex)
		return ejd.Finalize()
	})
	if err != nil {
		errors.Log(ctx, err)
		return 3
	}

	return 0
}
