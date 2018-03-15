package handler

import (
	"encoding/json"
	"go.chromium.org/luci/common/logging"

	"net/http"

	"infra/appengine/sheriff-o-matic/som/model"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/server/router"
)

// AnnotationTreeWorker attaches trees to annotations after the annotation
// schema was changed to include trees.
func AnnotationTreeWorker(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	q := datastore.NewQuery("Annotation")
	q = q.Gt("ModificationTime", clock.Get(c).Now().Add(-annotationExpiration))
	annotations := []*model.Annotation{}
	err := datastore.GetAll(c, q, &annotations)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	q = datastore.NewQuery("AlertJSON")
	q = q.Eq("Resolved", false)
	alerts := []*model.AlertJSON{}
	err = datastore.GetAll(c, q, &alerts)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	alertMap := make(map[string]*model.AlertJSON)
	for _, alert := range alerts {
		alertMap[alert.ID] = alert
	}

	for _, ann := range annotations {
		if alert, ok := alertMap[ann.Key]; ok {
			ann.Tree = alert.Tree
		}
	}

	err = datastore.Put(c, annotations)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	out, err := json.Marshal(annotations)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	logging.Infof(c, "%v", out)
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(out))

	return
}
