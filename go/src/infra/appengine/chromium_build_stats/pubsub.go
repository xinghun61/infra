// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package chromiumbuildstats

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"

	"cloud.google.com/go/storage"
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
	http.Handle("/pubsub", http.StripPrefix("/pubsub", http.HandlerFunc(pubsubHandler)))
}

func pubsubHandler(w http.ResponseWriter, req *http.Request) {
	ctx := appengine.NewContext(req)
	body, err := ioutil.ReadAll(req.Body)
	if err != nil {
		http.Error(w, "failed to read body request", http.StatusBadRequest)
		log.Errorf(ctx, "failed to read body request: %v", err)
		return
	}
	log.Debugf(ctx, "request : %v", string(body))

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

	info, err := getFile(ctx, filename, bucketID)
	if err != nil {
		http.Error(w, "failed to get file", http.StatusInternalServerError)
		log.Errorf(ctx, "failed to get file: %v", err)
		return
	}

	if err := sendToBigquery(ctx, *info); err != nil {
		http.Error(w, "failed to send BigQuery", http.StatusInternalServerError)
		log.Errorf(ctx, "failed to send BigQuery: %v", err)
		return
	}
	fmt.Fprintln(w, "OK")
}

/* fetch gcs upload file */
func getFile(ctx context.Context, filename string, bucketID string) (*ninjalog.NinjaLog, error) {
	// Creates a client.
	client, err := storage.NewClient(ctx)
	if err != nil {
		log.Errorf(ctx, "failed to create client: %v", err)
		return nil, err
	}
	defer func() {
		if err := client.Close(); err != nil {
			log.Warningf(ctx, "failed to close client: %v", err)
		}
	}()

	// Creates a Bucket instance.
	r, err := client.Bucket(bucketID).Object(filename).NewReader(ctx)
	if err != nil {
		log.Errorf(ctx, "failed to get reader: %v", err)
		return nil, err
	}
	defer func() {
		if err := r.Close(); err != nil {
			log.Warningf(ctx, "failed to close client: %v", err)
		}
	}()

	info, err := ninjalog.Parse(filename, r)
	if err != nil {
		log.Errorf(ctx, "failed to parse ninjalog: %v", err)
		return nil, err
	}
	return info, nil
}
