// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Binary cloudbuildhelper is used internally by Infra CI pipeline to build
// docker images.
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/hardcoded/chromeinfra"

	"infra/cmd/cloudbuildhelper/registry"
)

func main() {
	ctx := context.Background()

	// TODO(vadimsh): This is temporary.

	if len(os.Args) < 2 || len(os.Args) > 3 {
		log.Fatalf("Expecting one or two arguments")
	}

	opts := chromeinfra.DefaultAuthOptions()
	opts.Scopes = []string{"https://www.googleapis.com/auth/cloud-platform"}
	a := auth.NewAuthenticator(ctx, auth.SilentLogin, opts)
	ts, err := a.TokenSource()
	if err != nil {
		log.Fatalf("%s", err)
	}

	reg := registry.Client{TokenSource: ts}
	img, err := reg.GetImage(ctx, os.Args[1])
	if err != nil {
		log.Fatalf("%s", err)
	}
	fmt.Printf("%s\n", img.Reference())

	if len(os.Args) > 2 {
		tag := os.Args[2]
		fmt.Printf("Pushing it as %q\n", tag)
		if err := reg.TagImage(ctx, img, tag); err != nil {
			log.Fatalf("%s", err)
		}
		fmt.Println("Done!")
	}
}
