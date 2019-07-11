// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"flag"

	"github.com/maruel/subcommands"
)

type baseRun struct {
	subcommands.CommandRunBase
	topic     string
	project   string
	credsFile string
}

func (c *baseRun) registerCommonFlags(fs *flag.FlagSet) {
	fs.StringVar(&c.topic, "topic", "", "Pubsub topic to use")
	fs.StringVar(&c.project, "project", "", "Pubsub project to use")
}

func bytesMapToList(m map[string][]byte) [][]byte {
	l := make([][]byte, 0, len(m))
	for _, v := range m {
		l = append(l, v)
	}
	return l
}
