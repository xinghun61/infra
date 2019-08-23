// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"io/ioutil"

	"cloud.google.com/go/pubsub"
	"go.chromium.org/luci/common/flag"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/cli"
)

type publishRun struct {
	baseRun
	messageFile string
	attributes  map[string]string
}

// CmdPublish describes the subcommand flags for publishing messages
var CmdPublish = &subcommands.Command{
	UsageLine: "publish -project [PROJECT] -topic [TOPIC] [OPTIONS]",
	ShortDesc: "publish a message to a topic",
	CommandRun: func() subcommands.CommandRun {
		c := &publishRun{}
		c.registerCommonFlags(&c.Flags)
		c.Flags.StringVar(&c.messageFile, "file", "", "path to file to send as message")
		c.Flags.Var(flag.JSONMap(&c.attributes), "attributes", "map of attributes to add to the message")
		return c
	},
}

func (c *publishRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)
	client, err := c.createClient(ctx)
	if err != nil {
		fmt.Fprintln(a.GetErr(), err)
		return 1
	}

	t := client.Topic(c.topic)
	defer t.Stop()

	message, err := c.getMessageBody()
	if err != nil {
		fmt.Fprintln(a.GetErr(), err)
		return 1
	}
	if err := Publish(ctx, t, message, c.attributes); err != nil {
		fmt.Fprintln(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *publishRun) getMessageBody() ([]byte, error) {
	message, err := ioutil.ReadFile(c.messageFile)
	if err != nil {
		return nil, err
	}
	return message, nil
}

// Publish publishes a bytestream message to a topic with specified attributes
func Publish(ctx context.Context, topic *pubsub.Topic, msg []byte, attrs map[string]string) error {
	result := topic.Publish(ctx, &pubsub.Message{
		Data:       msg,
		Attributes: attrs,
	})
	// Block until the result is returned and a server-generated
	// ID is returned for the published message. Discard the ID.
	_, err := result.Get(ctx)
	return err
}
