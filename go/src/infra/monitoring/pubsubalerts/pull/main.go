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
	"time"

	"infra/monitoring/messages"
	sompubsub "infra/monitoring/pubsubalerts"

	"golang.org/x/net/context"

	"cloud.google.com/go/pubsub"
	"google.golang.org/api/iterator"
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

	it, err := sub.Pull(ctx, pubsub.MaxExtension(time.Minute))
	if err != nil {
		log.Fatalf("error constructing iterator: %v", err)
	}

	defer it.Stop()

	// Stop pulling messages from the topic if the OS interrupts us (e.g. user
	// hits ctrl-c).
	go func() {
		<-quit
		it.Stop()
	}()

	for i := 0; i < *numConsume; i++ {
		m, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			log.Fatalf("advancing iterator: %v", err)
			m.Done(false)
			break
		}

		reader, err := zlib.NewReader(bytes.NewReader(m.Data))
		if err != nil {
			log.Fatalf("zlib decoding: %v", err)
			m.Done(false)
			break
		}
		dec := json.NewDecoder(reader)
		extract := buildMasterMsg{}
		if err = dec.Decode(&extract); err != nil {
			log.Fatalf("json decoding: %v", err)
			m.Done(false)
			break
		}

		handler := &sompubsub.BuildHandler{Store: sompubsub.NewInMemAlertStore()}
		for _, b := range extract.Builds {
			err := handler.HandleBuild(ctx, b)
			if err != nil {
				log.Fatalf("error: %+v", err)
			}
		}

		m.Done(true)
	}
}
