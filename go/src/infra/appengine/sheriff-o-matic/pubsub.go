package som

import (
	"bytes"
	"compress/zlib"
	"encoding/json"
	"fmt"
	"net/http"

	"infra/monitoring/messages"
	sompubsub "infra/monitoring/pubsubalerts"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
)

// This is what we get from the Data field of the pubsub push request body.
type buildMasterMsg struct {
	Master *messages.BuildExtract `json:"master"`
	Builds []*messages.Build      `json:"builds"`
}

type pushMessage struct {
	Attributes map[string]string
	Data       []byte
	ID         string `json:"message_id"`
}

type pushRequest struct {
	Message      pushMessage
	Subscription string
}

func postMiloPubSubHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	msg := &pushRequest{}
	if err := json.NewDecoder(r.Body).Decode(msg); err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("Could not json decode body: %v", err))
		return
	}

	reader, err := zlib.NewReader(bytes.NewReader(msg.Message.Data))
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("Could not zlib decode message data: %v", err))
		return
	}

	dec := json.NewDecoder(reader)
	extract := buildMasterMsg{}
	if err = dec.Decode(&extract); err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("Could not decode build extract: %v", err))
		return
	}

	if len(extract.Builds) == 0 {
		return
	}

	logging.Debugf(c, "Contains %d builds for %d builders.", len(extract.Builds), len(extract.Master.Builders))

	// TODO(seanmccullough): Replace this the persistent store. This is here just to evaluate
	// a single milo push message without any other context.
	inMemAlerts := sompubsub.NewInMemAlertStore()
	miloPubSubHandler := &sompubsub.BuildHandler{Store: inMemAlerts}

	for _, b := range extract.Builds {
		if err := miloPubSubHandler.HandleBuild(b); err != nil {
			errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("Could not handle build extract: %v", err))
			return
		}
	}

	logging.Debugf(c, "Generated %d alerts.", len(inMemAlerts.StoredAlerts))
	w.Write([]byte("ok"))
}
