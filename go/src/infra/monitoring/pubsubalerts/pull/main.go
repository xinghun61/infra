// pull is a command line utility to run a pubsub pull subscriber for local
// debugging on a dev machine.  It uses the same alerge generating logic as
// the (eventual) push subscriber that will be deployed to appengine.
package main

import (
	"bytes"
	"compress/zlib"
	"encoding/json"
	"flag"
	"log"
	"os"
	"os/signal"
	"sync/atomic"
	"time"

	"infra/monitoring/messages"
	sompubsub "infra/monitoring/pubsubalerts"

	"golang.org/x/net/context"

	"cloud.google.com/go/pubsub"
)

var (
	projID     = flag.String("p", "luci-milo", "The ID of your Google Cloud project.")
	subName    = flag.String("s", "som-dev", "The name of the subscription to pull from")
	numConsume = flag.Int("n", 10, "The number of messages to consume")
)

// This is what we pull off the pubsub topic.
type buildMasterMsg struct {
	Master *messages.BuildExtract `json:"master"`
	Builds []*messages.Build      `json:"builds"`
}

func main() {
	flag.Parse()

	if *projID == "" {
		log.Fatal("-p is required")
	}
	if *subName == "" {
		log.Fatal("-s is required")
	}

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt)

	ctx := context.Background()

	client, err := pubsub.NewClient(ctx, *projID)
	if err != nil {
		log.Fatalf("creating pubsub client: %v", err)
	}

	sub := client.Subscription(*subName)
	sub.ReceiveSettings.MaxExtension = time.Minute
	sub.ReceiveSettings.MaxOutstandingMessages = 1 // Process one at a time.

	subCtx, cancelFunc := context.WithCancel(ctx)
	defer cancelFunc()

	// Stop pulling messages from the topic if the OS interrupts us (e.g. user
	// hits ctrl-c).
	go func() {
		<-quit
		cancelFunc()
	}()

	remainingConsume := int32(*numConsume)
	err = sub.Receive(subCtx, func(_ context.Context, msg *pubsub.Message) {
		// Handle this message. Note that we pass the OUTER Context here, which will
		// not be cancelled if subCtx is cancelled.
		wasError := handleMessage(ctx, msg)
		if !wasError {
			msg.Ack()
		} else {
			msg.Nack()
			cancelFunc()
		}

		// If we've hit our consumption limit, stop receiving additional messages.
		if atomic.AddInt32(&remainingConsume, -1) <= 0 {
			// Cancel JUST our subscription Context. Our outer Context, "ctx", will
			// not be canceled by this.
			cancelFunc()
		}
	})
	if err != nil {
		log.Fatalf("failed to Receive on Subscription: %s", err)
	}
}

// handleMessage handles the supplied Pub/Sub message. It returns true if the
// message was successfully handled, and false if it was not.
func handleMessage(ctx context.Context, msg *pubsub.Message) bool {
	reader, err := zlib.NewReader(bytes.NewReader(msg.Data))
	if err != nil {
		log.Printf("error: zlib decoding [%s]: %v", msg.ID, err)
		return false
	}
	dec := json.NewDecoder(reader)
	extract := buildMasterMsg{}
	if err = dec.Decode(&extract); err != nil {
		log.Printf("error: json decoding [%s]: %v", msg.ID, err)
		return false
	}

	// Handle our build via Handler. Note that this passes the OUTER Context,
	// which will not be cancelled if "subCtx" is cancelled.
	handler := &sompubsub.BuildHandler{Store: sompubsub.NewInMemAlertStore()}
	for _, b := range extract.Builds {
		err := handler.HandleBuild(ctx, b)
		if err != nil {
			log.Printf("error: handling [%s]: %+v", msg.ID, err)
			return false
		}
	}

	return true
}
