// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package app

import (
	"compress/gzip"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"math/rand"
	"net/http"
	"path"
	"strings"
	"time"

	"cloud.google.com/go/storage"
	"github.com/GoogleCloudPlatform/google-cloud-go-testing/storage/stiface"
	pubsub "google.golang.org/api/pubsub/v1"
	"google.golang.org/appengine"
	"google.golang.org/appengine/log"

	"infra/appengine/chromium_build_stats/ninjalog"
)

// Req is parsed data of http request.
type Req struct {
	pubsub.PubsubMessage `json:"message"`
}

func init() {
	rand.Seed(time.Now().UnixNano())
	http.Handle("/_ah/push-handlers/pubsub", http.HandlerFunc(pubsubHandler))
}

func pubsubHandler(w http.ResponseWriter, req *http.Request) {
	ctx := appengine.NewContext(req)
	body, err := ioutil.ReadAll(req.Body)
	if err != nil {
		http.Error(w, "failed to read body request", http.StatusBadRequest)
		log.Errorf(ctx, "failed to read body request: %v", err)
		return
	}
	log.Debugf(ctx, "request: %v", string(body))

	request := Req{}
	if err := json.Unmarshal(body, &request); err != nil {
		http.Error(w, "failed to decode json", http.StatusBadRequest)
		log.Errorf(ctx, "failed to decode json: %v", err)
		return
	}
	log.Debugf(ctx, "pub/sub message request: %v", request.PubsubMessage.Attributes)
	// when GCS file event is not create event type.
	if request.PubsubMessage.Attributes["eventType"] != storage.ObjectFinalizeEvent {
		log.Debugf(ctx, "not create event: %v", request.PubsubMessage.Attributes["eventType"])
		fmt.Fprintln(w, "Object is not create!")
		return
	}

	filename := request.PubsubMessage.Attributes["objectId"]
	bucketID := request.PubsubMessage.Attributes["bucketId"]
	log.Debugf(ctx, "objectId: %v, bucketId: %v", filename, bucketID)

	if rand.Intn(10) != 0 {
		fmt.Fprintln(w, "OK")
		log.Infof(ctx, "request is skipped")
		return
	}

	basename := path.Base(filename)
	if !strings.HasPrefix(basename, "ninja_log") {
		log.Debugf(ctx, "not ninjalog file: %v", filename)
		fmt.Fprintln(w, "This is not ninjalog file!")
		return
	}

	info, err := getFile(ctx, filename, bucketID)
	if err != nil {
		http.Error(w, "failed to get file", http.StatusInternalServerError)
		log.Errorf(ctx, "failed to get file: %v", err)
		return
	}

	if err := SendToBigquery(ctx, info); err != nil {
		http.Error(w, "failed to send BigQuery", http.StatusInternalServerError)
		log.Errorf(ctx, "failed to send BigQuery: %v", err)
		return
	}
	fmt.Fprintln(w, "OK")
}

var createAdaptClient = stiface.AdaptClient
var createClient = storage.NewClient

// getFile fetches GCS upload file.
func getFile(ctx context.Context, filename string, bucketID string) (*ninjalog.NinjaLog, error) {
	// Creates a client.
	client, err := createClient(ctx)
	if err != nil {
		log.Errorf(ctx, "failed to create client: %v", err)
		return nil, err
	}
	defer func() {
		if err := client.Close(); err != nil {
			log.Warningf(ctx, "failed to close client: %v", err)
		}
	}()
	sclient := createAdaptClient(client)

	var reader io.ReadCloser
	// Creates a Bucket instance.
	reader, err = sclient.Bucket(bucketID).Object(filename).ReadCompressed(true).NewReader(ctx)
	if err != nil {
		log.Errorf(ctx, "failed to get reader: %v", err)
		return nil, err
	}
	closer := func(reader io.ReadCloser) {
		if err := reader.Close(); err != nil {
			log.Warningf(ctx, "failed to close client: %v", err)
		}
	}
	defer closer(reader)

	reader, err = gzip.NewReader(reader)
	if err != nil {
		log.Errorf(ctx, "failed to ungzip file: %v", err)
		return nil, err
	}
	defer closer(reader)

	info, err := ninjalog.Parse(filename, reader)
	if err != nil {
		log.Errorf(ctx, "failed to parse ninjalog: %v", err)
		return nil, err
	}
	return info, nil
}
