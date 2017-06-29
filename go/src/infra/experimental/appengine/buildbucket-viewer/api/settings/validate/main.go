// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"io/ioutil"
	"os"

	"infra/experimental/appengine/buildbucket-viewer/api/settings"

	"github.com/luci/luci-go/common/errors"

	"github.com/golang/protobuf/proto"
)

func main() {
	rv := 0
	for _, arg := range os.Args[1:] {
		if err := validateProjectConfig(arg); err != nil {
			fmt.Fprintf(os.Stderr, "Error validating [%s]: %v", arg, err)
			rv = 1
		} else {
			fmt.Println("Successfully validated:", arg)
		}
	}
	os.Exit(rv)
}

func validateProjectConfig(path string) error {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return errors.Annotate(err, "failed to read file").
			InternalReason("path(%s)", path).Err()
	}

	var pc settings.ProjectConfig
	if err := proto.UnmarshalText(string(data), &pc); err != nil {
		return errors.Annotate(err, "failed to unmarshal protobuf").Err()
	}

	return nil
}
