// Copyright 2015 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"os"

	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/logdog/client/cli"

	"infra/libs/infraenv"

	"golang.org/x/net/context"
)

func main() {
	mathrand.SeedRandomly()
	os.Exit(cli.Main(context.Background(), cli.Parameters{
		Args:               os.Args[1:],
		Host:               infraenv.ProdLogDogHost,
		DefaultAuthOptions: infraenv.DefaultAuthOptions(),
	}))
}
