// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package pubsublib

import (
	"context"
	"sync"
	"testing"

	"cloud.google.com/go/pubsub"
)

type dummyReceiver struct {
	input []pubsub.Message
}

func (r *dummyReceiver) Receive(ctx context.Context, handler func(context.Context, *pubsub.Message)) error {
	wg := sync.WaitGroup{}
	wg.Add(len(r.input))

	for _, m := range r.input {
		go func(msg pubsub.Message) {
			handler(ctx, &msg)
			wg.Done()
		}(m)
	}
	wg.Wait()
	<-ctx.Done()
	return ctx.Err()
}

var _ Receiver = &dummyReceiver{}

func newReceiver(queue []pubsub.Message) Receiver {
	return &dummyReceiver{
		input: queue,
	}
}

func TestReadOneMessage(t *testing.T) {
	in := []pubsub.Message{{}}
	s := newReceiver(in)
	ctx, can := context.WithCancel(context.Background())
	ch := ReceiveToChannel(ctx, s)
	defer can()
	var i int
	for moe := range ch {
		if moe.Error != nil {
			t.Fatalf("Error while reading messages to channel: %v\n", moe.Error)
		}
		if moe.Message != nil {
			i++
			break
		}
		t.Fatalf("Non-message, non-error found on channel. %v\n", moe)
	}
	if i != 1 {
		t.Fatalf("Expected 1 message, saw %v", i)
	}
}
