// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"time"

	"infra/cmd/cros/ipcpubsub/pubsublib"

	"cloud.google.com/go/pubsub"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag"
)

type subscribeRun struct {
	baseRun
	attributes   map[string]string
	messageCount int
	subName      string
	timeout      time.Duration
	outputDir    string
}

// CmdSubscribe describes the subcommand flags for subscribing to messages.
var CmdSubscribe = &subcommands.Command{
	UsageLine: "subscribe -project [PROJECT] -topic [TOPIC] -output [PATH/TO/OUTPUT/DIR] [OPTIONS]",
	ShortDesc: "subscribe to a filtered topic",
	CommandRun: func() subcommands.CommandRun {
		c := &subscribeRun{}
		c.registerCommonFlags(&c.Flags)
		c.Flags.Var(flag.JSONMap(&c.attributes), "attributes", "map of attributes to filter for")
		c.Flags.IntVar(&c.messageCount, "count", 1, "number of messages to read before returning")
		c.Flags.StringVar(&c.outputDir, "output", "", "path to directory to store output")
		c.Flags.StringVar(&c.subName, "sub-name", "", "name of subscription: must be 3-255 characters, start with a letter, and composed of alphanumerics and -_.~+% only")
		c.Flags.DurationVar(&c.timeout, "timeout", time.Hour, "timeout to stop waiting, ex. 10s, 5m, 1h30m")
		return c
	},
}

func (c *subscribeRun) validateArgs(ctx context.Context, a subcommands.Application, args []string, env subcommands.Env) error {
	if c.messageCount < 1 {
		return errors.Reason("message-count must be >0").Err()
	}
	if c.subName == "" {
		return errors.Reason("subscription name is required").Err()
	}
	minTimeout := 10 * time.Second
	if c.timeout < minTimeout {
		return errors.Reason("timeout must be >= 10s").Err()
	}
	return nil
}

func (c *subscribeRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)
	if err := c.validateArgs(ctx, a, args, env); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		c.Flags.Usage()
		return 1
	}
	client, err := pubsub.NewClient(ctx, c.project)
	if err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		return 1
	}
	sub := client.Subscription(c.subName)
	received, err := ReadMessages(ctx, sub, c.messageCount, c.attributes)
	if err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		return 1
	}
	// Do something with received messages.
	_ = received
	return 0
}

// subscribe pulls messageCount messages from the message stream msgs, returning each of them as unformatted bytes.
func subscribe(ctx context.Context, ch <-chan pubsublib.MessageOrError, messageCount int, filter map[string]string) ([][]byte, error) {
	storedMessages := map[string]pubsublib.Message{}

	for {
		if len(storedMessages) >= messageCount {
			return extractBodiesFromMap(storedMessages), nil
		}
		select {
		case <-ctx.Done():
			return nil, errors.New("subscribe ended without sufficient messages")
		case moe := <-ch:
			if moe.Error != nil {
				return nil, moe.Error
			}
			if moe.Message == nil {
				return nil, errors.New("malformed item on MessageOrError channel")
			}
			m := moe.Message
			if !matchesFilter(filter, m) {
				m.Ack()
				continue
			}
			storedMessages[m.ID()] = m
			m.Ack()
		}
	}
}

// ReadMessages pulls messages from a Cloud Pub/Sub subscription.
func ReadMessages(ctx context.Context, subscription *pubsub.Subscription, msgCount int, filter map[string]string) ([][]byte, error) {
	// Test coverage for ReadMessages is all in the form of tests for the two principal components, since the body of ReadMessages is minimal.
	cctx, cancel := context.WithCancel(ctx)
	defer cancel()
	ch := pubsublib.ReceiveToChannel(cctx, subscription)
	defer func() {
		go func() {
			for range ch {
			}
		}()
	}()
	received, err := subscribe(cctx, ch, msgCount, filter)
	if err != nil {
		return nil, err
	}
	return received, nil
}

func matchesFilter(f map[string]string, m pubsublib.Message) bool {
	a := m.Attributes()
	for k, v := range f {
		if a[k] != v {
			return false
		}
	}
	return true
}

func extractBodiesFromMap(m map[string]pubsublib.Message) [][]byte {
	lst := make([][]byte, len(m))
	var i int
	for _, v := range m {
		lst[i] = v.Body()
		i++
	}
	return lst
}
