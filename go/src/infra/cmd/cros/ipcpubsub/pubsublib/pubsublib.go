// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// pubsublib specifies an interface around pubsub.Message for testing purposes, implements
//  a wrapper type which implements that interface, and defines a ReceiveToChannel function which
//  transmits pubsub messages to a channel where they can be subscribed to in a data-hiding way.

package pubsublib

import (
	"context"

	"cloud.google.com/go/pubsub"
)

// Message describes the behaviors of a pubsub message.
type Message interface {
	Attributes() map[string]string
	Body() []byte
	ID() string
	Ack()
}

// Receiver is an interface wrapping pubsub.Subscription's Receive method.
type Receiver interface {
	Receive(context.Context, func(context.Context, *pubsub.Message)) error
}

var _ Receiver = &pubsub.Subscription{}

// realMessage wraps pubsub messages as a Message.
type realMessage struct {
	message *pubsub.Message
}

var _ Message = &realMessage{}

// Attributes of the message.
func (m *realMessage) Attributes() map[string]string {
	return m.message.Attributes
}

// Body of message, as unformatted bytes.
func (m *realMessage) Body() []byte {
	return m.message.Data
}

// ID is a unique message identifier to identify messages sent more than once.
func (m *realMessage) ID() string {
	return m.message.ID
}

func (m *realMessage) Ack() {
	m.message.Ack()
}

// MessageOrError is a wrapper type for channels which need to transmit both messages and errors.
type MessageOrError struct {
	Message Message
	Error   error
}

// ReceiveToChannel pulls messages from a subscription sub until it gets an error or its context is closed.
// It returns the channel for messages and/or errors and is never a blocking call.
func ReceiveToChannel(ctx context.Context, sub Receiver) <-chan MessageOrError {
	ch := make(chan MessageOrError)

	handler := func(c context.Context, m *pubsub.Message) {
		select {
		case <-c.Done():
		case ch <- MessageOrError{Message: &realMessage{message: m}}:
		}
	}
	go func() {
		err := sub.Receive(ctx, handler)
		if err != nil {
			ch <- MessageOrError{Error: err}
		}
		close(ch)
	}()
	return ch
}
