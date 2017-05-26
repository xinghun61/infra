// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os/exec"
	"strings"

	"golang.org/x/net/context"

	swarming "github.com/luci/luci-go/common/api/swarming/swarming/v1"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/isolatedclient"
	"github.com/luci/luci-go/common/logging"
)

func logCmd(ctx context.Context, arg0 string, args ...string) *exec.Cmd {
	ret := exec.CommandContext(ctx, arg0, args...)
	logging.Debugf(ctx, "Running - %s %v", arg0, args)
	return ret
}

func cmdErr(err error, reason string) error {
	if err != nil {
		ee, _ := err.(*exec.ExitError)
		outErr := ""
		if ee != nil {
			outErr = strings.TrimSpace(string(ee.Stderr))
			if len(outErr) > 128 {
				outErr = outErr[:128] + "..."
			}
		}
		err = errors.Annotate(err).
			Reason(reason+": %(outErr)s").
			D("outErr", outErr).Err()
	}
	return err
}

func getIsolatedFlags(s *swarming.Service) (isolatedclient.Flags, error) {
	details, err := s.Server.Details().Do()
	if err != nil {
		return isolatedclient.Flags{}, err
	}
	return isolatedclient.Flags{
		ServerURL: details.DefaultIsolateServer,
		Namespace: details.DefaultIsolateNamespace,
	}, nil
}
