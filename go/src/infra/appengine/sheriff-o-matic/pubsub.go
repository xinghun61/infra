package som

import (
	"bytes"
	"compress/zlib"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"

	"infra/monitoring/messages"
	sompubsub "infra/monitoring/pubsubalerts"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/memcache"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
)

const (
	gatekeeperTreesKey = "gatekeeper_trees.json"
	gkTreesURL         = "https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/gatekeeper_trees.json?format=text"
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
		logging.Errorf(c, "Could not json decode body: %v", err)
		return
	}

	reader, err := zlib.NewReader(bytes.NewReader(msg.Message.Data))
	if err != nil {
		logging.Errorf(c, "Could not zlib decode message data: %v", err)
		return
	}

	dec := json.NewDecoder(reader)
	extract := buildMasterMsg{}
	if err = dec.Decode(&extract); err != nil {
		logging.Errorf(c, "Could not decode build extract: %v", err)
		return
	}

	if len(extract.Builds) == 0 {
		return
	}

	if extract.Master != nil {
		logging.Debugf(c, "Contains %d builds for %d builders.", len(extract.Builds), len(extract.Master.Builders))
	}

	store := sompubsub.NewAlertStore()
	miloPubSubHandler := &sompubsub.BuildHandler{Store: store}

	for _, b := range extract.Builds {
		if err := miloPubSubHandler.HandleBuild(c, b); err != nil {
			logging.Errorf(c, "Could not handle build: %v", err)
		}
	}

	w.Write([]byte("ok"))
}

func getPubSubAlertsHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	tree := p.ByName("tree")

	store := sompubsub.NewAlertStore()
	trees, err := getGatekeeperTrees(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	treeCfg, ok := trees[tree]
	if !ok {
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("Unrecoginzed tree: %s", tree))
		return
	}

	activeAlerts := []*messages.Alert{}

	for masterLoc := range treeCfg.Masters {
		alerts, err := store.ActiveAlertsForBuilder(c, masterLoc.Name(), "")
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}
		for _, a := range alerts {
			alert := &messages.Alert{
				// TODO(seanmccullough): Fill out the rest of this with actual
				// failure details etc.
				Title: a.Signature,
			}
			activeAlerts = append(activeAlerts, alert)
		}
	}

	b, err := json.Marshal(activeAlerts)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(b)
}

// TODO(seanmccullough): Replace this urlfetch/memcache code with a luci-config reader.
// Blocked on https://bugs.chromium.org/p/chromium/issues/detail?id=658270
var getGatekeeperTrees = func(c context.Context) (map[string]*messages.TreeMasterConfig, error) {
	item, err := memcache.GetKey(c, gatekeeperTreesKey)
	if err != nil && err != memcache.ErrCacheMiss {
		return nil, err
	}

	var b []byte
	if err == memcache.ErrCacheMiss {
		b, err = refreshGatekeeperTrees(c)
		item = memcache.NewItem(c, gatekeeperTreesKey).SetValue(b)
		err = memcache.Set(c, item)
	}

	if err != nil {
		return nil, err
	}

	ret := make(map[string]*messages.TreeMasterConfig)

	if err := json.Unmarshal(item.Value(), &ret); err != nil {
		return nil, err
	}

	return ret, nil
}

func refreshGatekeeperTrees(c context.Context) ([]byte, error) {
	client := &http.Client{Transport: urlfetch.Get(c)}

	resp, err := client.Get(gkTreesURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP status code %d from %s", resp.StatusCode, resp.Request.URL)
	}

	reader := base64.NewDecoder(base64.StdEncoding, resp.Body)
	b, err := ioutil.ReadAll(reader)
	if err != nil {
		return nil, err
	}

	return b, nil
}
