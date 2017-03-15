// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package driver implements HTTP handlers to the driver module.
package driver

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"net/http"

	"github.com/golang/protobuf/proto"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"

	"golang.org/x/net/context"

	"google.golang.org/api/googleapi"
	"google.golang.org/api/pubsub/v1"
	"google.golang.org/appengine"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

func triggerHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[driver] Trigger queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	tr := &admin.TriggerRequest{}
	if err := proto.Unmarshal(body, tr); err != nil {
		logging.WithError(err).Errorf(c, "[driver] Trigger queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[driver] Trigger request (run ID: %d, Worker: %s)", tr.RunId, tr.Worker)
	if _, err := server.Trigger(c, tr); err != nil {
		logging.WithError(err).Errorf(c, "[driver] Failed to call Driver.Trigger")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	logging.Infof(c, "[driver] Successfully completed trigger")
	w.WriteHeader(http.StatusOK)
}

func collectHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "[driver] Collect queue handler failed to read request body")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	cr := &admin.CollectRequest{}
	if err := proto.Unmarshal(body, cr); err != nil {
		logging.WithError(err).Errorf(c, "[driver] Collect queue handler failed to unmarshal request")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[driver] Collect request (run ID: %d, Worker: %s)", cr.RunId, cr.Worker)
	if _, err := server.Collect(c, cr); err != nil {
		logging.WithError(err).Errorf(c, "[driver] Failed to call Driver.Collect")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	logging.Infof(c, "[driver] Successfully completed collect")
	w.WriteHeader(http.StatusOK)
}

func pubsubPushHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	logging.Infof(c, "[driver] Received pubsub push message")
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to read pubsub message body: %v", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	var pushBody struct {
		Message pubsub.PubsubMessage `json:"message"`
	}
	if err := json.Unmarshal(body, &pushBody); err != nil {
		logging.WithError(err).Errorf(c, "failed to unmarshal JSON pubsub message: %v", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	// Process pubsub message
	if err := handlePubSubMessage(c, &pushBody.Message); err != nil {
		logging.WithError(err).Errorf(c, "failed to handle PubSub message: %v", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Infof(c, "[driver] Successfully processed PubSub push notification")
	w.WriteHeader(http.StatusOK)
}

func pubsubPullHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	if !appengine.IsDevAppServer() {
		logging.Errorf(c, "PubSub pull only supported on devserver")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// TODO(emso): compose from info.AppID(c), always use tricium-dev for devserver.
	topic := "projects/tricium-dev/topics/worker-completion"
	sub := "projects/tricium-dev/subscriptions/workstation-subscriber"

	transport, err := auth.GetRPCTransport(c, auth.AsSelf, auth.WithScopes(pubsub.PubsubScope))
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to create HTTP transport: %v", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	service, err := pubsub.New(&http.Client{Transport: transport})
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to create HTTP client: %v", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// Create the subscription to this topic. Ignore HTTP 409.
	logging.Infof(c, "[driver] Ensuring subscription %q exists", sub)
	_, err = service.Projects.Subscriptions.Create(sub, &pubsub.Subscription{
		Topic:              topic,
		AckDeadlineSeconds: 70, // GAE request timeout plus some spare time
		PushConfig: &pubsub.PushConfig{
			PushEndpoint: "", // if "", the subscription will be pull based
		},
	}).Context(c).Do()
	if err != nil && !isHTTP409(err) {
		logging.WithError(err).Errorf(c, "failed to check subscription: %v", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// Pull one message
	resp, err := service.Projects.Subscriptions.Pull(sub, &pubsub.PullRequest{
		ReturnImmediately: true,
		MaxMessages:       1,
	}).Context(c).Do()
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to pull PubSub message: %v", err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	var msg *pubsub.PubsubMessage
	var ack func()
	switch len(resp.ReceivedMessages) {
	case 0:
		logging.Infof(c, "found no PubSub messages")
		w.WriteHeader(http.StatusOK)
		return
	case 1:
		ackID := resp.ReceivedMessages[0].AckId
		ack = func() {
			_, err := service.Projects.Subscriptions.Acknowledge(sub, &pubsub.AcknowledgeRequest{
				AckIds: []string{ackID},
			}).Context(c).Do()
			if err != nil {
				logging.WithError(err).Errorf(c, "failed to acknowledge PubSub message: %v", err)
			}
		}
		msg = resp.ReceivedMessages[0].Message
		logging.Infof(c, "[driver] Pulled PubSub message")
	default:
		panic(errors.New("received more than one message from PubSub while asking for only one"))
	}

	// Process pubsub message
	if err := handlePubSubMessage(c, msg); err != nil {
		logging.WithError(err).Errorf(c, "failed to handle PubSub messages: %v", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	ack()
	logging.Infof(c, "[driver] Successfully completed PubSub pull")
	w.WriteHeader(http.StatusOK)
}

func isHTTP409(err error) bool {
	apiErr, _ := err.(*googleapi.Error)
	return apiErr != nil && apiErr.Code == 409
}

type payload struct {
	TaskID   string `json:"task_id"`
	Userdata string `json:"userdata"`
}

func handlePubSubMessage(c context.Context, msg *pubsub.PubsubMessage) error {
	logging.Infof(c, "[driver] Received pubsub message, messageId: %q, publishTime: %q", msg.MessageId, msg.PublishTime)
	tr, taskID, err := decodePubsubMessage(c, msg)
	if err != nil {
		return fmt.Errorf("failed to decode pubsub message: %v", err)
	}
	logging.Infof(c, "[driver] Unwrapped pubsub message, task ID: %q, TriggerRequest: %v", taskID, tr)
	// Enqueue collect request
	b, err := proto.Marshal(&admin.CollectRequest{
		RunId:             tr.RunId,
		IsolateServerUrl:  tr.IsolateServerUrl,
		IsolatedInputHash: tr.IsolatedInputHash,
		Worker:            tr.Worker,
		SwarmingServerUrl: tr.SwarmingServerUrl,
		TaskId:            taskID,
	})
	if err != nil {
		return fmt.Errorf("failed to marshal collect request: %v", err)
	}
	t := tq.NewPOSTTask("/driver/internal/collect", nil)
	t.Payload = b
	if err := tq.Add(c, common.DriverQueue, t); err != nil {
		return fmt.Errorf("failed to enqueue collect request: %v", err)
	}
	logging.Infof(c, "[driver] Enqueued collect request, runID: %d, worker: %s", tr.RunId, tr.Worker)
	return nil
}

// decodePubsubMessage decodes the provided PubSub message to a TriggerRequest and a task ID.
//
// The pubsub message published to the worker completion topic from Swarming should
// include a serialized proto TriggerRequest that has been base64 encoded and included
// as userdata in the Swarming trigger request. In addition, Swarming adds the task ID of the
// completed task.
func decodePubsubMessage(c context.Context, msg *pubsub.PubsubMessage) (*admin.TriggerRequest, string, error) {
	data, err := base64.StdEncoding.DecodeString(msg.Data)
	if err != nil {
		return nil, "", fmt.Errorf("failed to base64 decode pubsub message: %v", err)
	}
	p := payload{}
	if err := json.Unmarshal(data, &p); err != nil {
		return nil, "", fmt.Errorf("failed to unmarshal pubsub JSON playload: %v", err)
	}
	userdata, err := base64.StdEncoding.DecodeString(p.Userdata)
	if err != nil {
		return nil, "", fmt.Errorf("failed to base64 decode pubsub userdata: %v", err)
	}
	tr := &admin.TriggerRequest{}
	if err := proto.Unmarshal([]byte(userdata), tr); err != nil {
		return nil, "", fmt.Errorf("failed to unmarshal pubsub proto userdata: %v", err)
	}
	return tr, p.TaskID, nil
}
