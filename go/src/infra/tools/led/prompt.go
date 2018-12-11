// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

// +build !windows

package main

import (
	"fmt"
	"os"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
)

func prompt(ctx context.Context) error {
	// TODO(iannucci): make this work on windows
	logging.Infof(ctx, "When finished, press <enter> here to isolate it.")

	tty, err := os.Open("/dev/tty")
	if err != nil {
		return errors.Annotate(err, "opening /dev/tty").Err()
	}
	defer tty.Close()

	fmt.Fscanln(tty)

	return nil
}
