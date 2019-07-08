// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"time"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"google.golang.org/api/pubsub/v1"
	"google.golang.org/appengine"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/appengine/common"
)

var driver = driverServer{}

func triggerHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to read request body.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	tr := &admin.TriggerRequest{}
	if err := proto.Unmarshal(body, tr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to unmarshal request.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Fields{
		"runID":  tr.RunId,
		"worker": tr.Worker,
	}.Infof(c, "Request received.")
	if _, err := driver.Trigger(c, tr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to call Trigger.")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	w.WriteHeader(http.StatusOK)
}

func collectHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to read request body.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	cr := &admin.CollectRequest{}
	if err := proto.Unmarshal(body, cr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to unmarshal request.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	logging.Fields{
		"runID":  cr.RunId,
		"worker": cr.Worker,
	}.Infof(c, "Request received.")
	if _, err := driver.Collect(c, cr); err != nil {
		logging.WithError(err).Errorf(c, "Failed to call Collect.")
		switch grpc.Code(err) {
		case codes.InvalidArgument:
			w.WriteHeader(http.StatusBadRequest)
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
		return
	}
	w.WriteHeader(http.StatusOK)
}

// TODO(crbug/877303): We should set up a separate endpoint for swarming and buildbucket
// pubsub handlers, as they are similar but subtly different enough to merit separating
// the two rather than handling them in the same function.
func pubsubPushHandler(ctx *router.Context) {
	c, r, w := ctx.Context, ctx.Request, ctx.Writer
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to read PubSub message body.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	var pushBody struct {
		Message pubsub.PubsubMessage `json:"message"`
	}
	if err := json.Unmarshal(body, &pushBody); err != nil {
		logging.WithError(err).Errorf(c, "Failed to unmarshal JSON PubSub message.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	// Process pubsub message.
	if err := handlePubSubMessage(c, &pushBody.Message); err != nil {
		logging.WithError(err).Errorf(c, "Failed to handle PubSub message.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	w.WriteHeader(http.StatusOK)
}

func pubsubPullHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	// Only run pull on the dev server.
	if !appengine.IsDevAppServer() {
		logging.Errorf(c, "PubSub pull only supported on devserver.")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	// Pull PubSub message.
	msg, err := common.PubsubServer.Pull(c)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to pull PubSub message.")
		w.WriteHeader(http.StatusOK) // there may not be a message to pull yet so not an error
		return
	}
	if msg == nil {
		logging.Infof(c, "Found no PubSub message.")
		w.WriteHeader(http.StatusOK)
		return
	}
	logging.Infof(c, "Pulled PubSub message.")
	// Process PubSub message.
	if err := handlePubSubMessage(c, msg); err != nil {
		logging.WithError(err).Errorf(c, "Failed to handle PubSub messages.")
		w.WriteHeader(http.StatusBadRequest)
		return
	}
	w.WriteHeader(http.StatusOK)
}

// ReceivedPubSubMessage guards against duplicate processing of pubsub messages.
//
// LUCI datastore ID (=<swarming task ID/buildbucket build ID>:run ID) field.
type ReceivedPubSubMessage struct {
	ID     string `gae:"$id"`
	RunID  int64
	Worker string
}

func handlePubSubMessage(c context.Context, msg *pubsub.PubsubMessage) error {
	logging.Fields{
		"messageID":   msg.MessageId,
		"publishTime": msg.PublishTime,
	}.Infof(c, "PubSub message received.")
	tr, taskID, buildID, err := decodePubsubMessage(c, msg)
	if err != nil {
		return errors.Annotate(err, "failed to decode PubSub message").Err()
	}
	logging.Fields{
		"buildID":        buildID,
		"taskID":         taskID,
		"TriggerRequest": tr,
	}.Infof(c, "Unwrapped PubSub message.")
	// Check if message was already received.
	received := &ReceivedPubSubMessage{}
	if taskID != "" {
		received.ID = fmt.Sprintf("%s:%d", taskID, tr.RunId)
	} else {
		received.ID = fmt.Sprintf("%d:%d", buildID, tr.RunId)
	}
	err = ds.Get(c, received)
	if err != nil && err != ds.ErrNoSuchEntity {
		return errors.Annotate(err, "failed to get receivedPubSubMessage").Err()
	}
	// If message not already received, store to prevent duplicate processing.
	if err == ds.ErrNoSuchEntity {
		received.RunID = tr.RunId
		received.Worker = tr.Worker
		if err = ds.Put(c, received); err != nil {
			return errors.Annotate(err, "failed to store receivedPubSubMessage").Err()
		}
	} else {
		logging.Fields{
			"buildID": buildID,
			"taskID":  taskID,
		}.Infof(c, "Skipping processing of PubSub message.")
		// Message has already been processed, return and ack the
		// PubSub message with no further action.
		return nil
	}
	// Enqueue a new collect request to be executed immediately.
	err = enqueueCollectRequest(c, &admin.CollectRequest{
		RunId:             tr.RunId,
		IsolatedInputHash: tr.IsolatedInputHash,
		Worker:            tr.Worker,
		TaskId:            taskID,
		BuildId:           buildID,
	}, 0)
	if err != nil {
		return err
	}
	logging.Fields{
		"runID":  tr.RunId,
		"worker": tr.Worker,
	}.Infof(c, "Enqueued collect request.")
	return nil
}

// enqueueCollectRequest enqueue a collect request to execute after a delay.
//
// Besides being used to enqueue the initial collect request after receiving a
// PubSub message, this may also be used to retry collect requests for workers
// that are not yet finished.
func enqueueCollectRequest(c context.Context, request *admin.CollectRequest, delay time.Duration) error {
	b, err := proto.Marshal(request)
	if err != nil {
		return errors.Annotate(err, "failed to marshal collect request").Err()
	}
	t := tq.NewPOSTTask("/driver/internal/collect", nil)
	t.Payload = b
	t.Delay = delay
	if err := tq.Add(c, common.DriverQueue, t); err != nil {
		return errors.Annotate(err, "failed to enqueue collect request").Err()
	}
	return nil
}

// decodePubsubMessage decodes the provided PubSub message to a TriggerRequest
// and a task ID or build ID.
//
// The pubsub message published to the worker completion topic from Swarming
// should include a serialized proto TriggerRequest that has been base64
// encoded and included as userdata in the Swarming trigger request. In
// addition, Swarming adds the task ID of the completed task or Buildbucket
// adds the build ID of the completed build.
func decodePubsubMessage(c context.Context, msg *pubsub.PubsubMessage) (*admin.TriggerRequest, string, int64, error) {
	data, err := base64.StdEncoding.DecodeString(msg.Data)
	if err != nil {
		return nil, "", 0, errors.Annotate(err, "failed to base64 decode pubsub message").Err()
	}

	p := struct {
		Build struct {
			ID int64 `json:"id,string"`
		} `json:"build"`
		TaskID              string `json:"task_id"`
		Userdata            string `json:"userdata"`
		BuildbucketUserdata string `json:"user_data"`
	}{}
	if err = json.Unmarshal(data, &p); err != nil {
		return nil, "", 0, errors.Annotate(err, "failed to unmarshal pubsub JSON payload").Err()
	}
	var rawUserdata string
	if p.Userdata == "" {
		rawUserdata = p.BuildbucketUserdata
	} else {
		rawUserdata = p.Userdata
	}
	userdata, err := base64.StdEncoding.DecodeString(rawUserdata)
	if err != nil {
		return nil, "", 0, errors.Annotate(err, "failed to base64 decode pubsub userdata").Err()
	}
	tr := &admin.TriggerRequest{}
	if err := proto.Unmarshal([]byte(userdata), tr); err != nil {
		return nil, "", 0, errors.Annotate(err, "failed to unmarshal pubsub proto userdata").Err()
	}
	return tr, p.TaskID, p.Build.ID, nil
}
