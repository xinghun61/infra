// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to default module.
package som

import (
	"crypto/sha1"
	"encoding/json"
	"fmt"
	"html/template"
	"infra/monorail"
	"io/ioutil"
	"net/http"
	"strings"

	"golang.org/x/net/context"
	"google.golang.org/appengine"

	"github.com/luci/gae/impl/prod"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/appengine/gaeauth/client"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/identity"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/settings"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	gaeurlfetch "google.golang.org/appengine/urlfetch"
)

const authGroup = "sheriff-o-matic-access"

var (
	mainPage         = template.Must(template.ParseFiles("./index.html"))
	accessDeniedPage = template.Must(template.ParseFiles("./access-denied.html"))
	monorailEndpoint = "https://monorail-prod.appspot.com/_ah/api/monorail/v1/"
)

var errStatus = func(w http.ResponseWriter, status int, msg string) {
	w.WriteHeader(status)
	w.Write([]byte(msg))
}

var requireGoogler = func(w http.ResponseWriter, c context.Context) bool {
	if appengine.IsDevAppServer() {
		return true
	}

	isMember, err := auth.IsMember(c, authGroup)
	if !isMember || err != nil {
		msg := ""
		if !isMember {
			msg = "Access Denied"
		} else {
			msg = err.Error()
		}

		errStatus(w, http.StatusForbidden, msg)
		return false
	}
	return true
}

const settingsKey = "tree"

type settingsUIPage struct {
	settings.BaseUIPage
}

func (settingsUIPage) Title(c context.Context) (string, error) {
	return "Admin SOM settings", nil
}

func (settingsUIPage) Fields(c context.Context) ([]settings.UIField, error) {
	return []settings.UIField{
		{
			ID:    "Trees",
			Title: "Trees in SOM",
			Type:  settings.UIFieldText,
			Help:  "Trees listed in SOM. Comma separated values.",
		},
		{
			ID:    "AlertStreams",
			Title: "Alert streams",
			Type:  settings.UIFieldText,
			Help:  "Alert streams per each tree. Write only field; tree:streamA,streamB",
		},
		{
			ID:    "BugQueueLabels",
			Title: "Bug queue labels",
			Type:  settings.UIFieldText,
			Help:  "Bug queue label for each tree. Write only field; treeA:queueA,treeB:queueB",
		},
	}, nil
}

func (settingsUIPage) ReadSettings(c context.Context) (map[string]string, error) {
	q := datastore.NewQuery("Tree")
	results := []*Tree{}
	datastore.Get(c).GetAll(q, &results)
	stringed := make([]string, len(results))
	for i, tree := range results {
		stringed[i] = tree.Name
	}

	return map[string]string{
		"Trees":        strings.Join(stringed, ","),
		"AlertStreams": "",
	}, nil
}

func writeTrees(c context.Context, treeStr string) error {
	ds := datastore.Get(c)
	q := datastore.NewQuery("Tree")
	trees := []*Tree{}
	datastore.Get(c).GetAll(q, &trees)

	toMake := strings.Split(treeStr, ",")
	for _, tree := range trees {
		for i, it := range toMake {
			if it == tree.Name {
				toMake[i] = ""
			}
		}
	}

	for _, it := range toMake {
		it = strings.TrimSpace(it)
		if len(it) == 0 {
			continue
		}

		if err := ds.Put(&Tree{
			Name:        it,
			DisplayName: strings.Replace(strings.Title(it), "_", " ", -1),
		}); err != nil {
			return err
		}
	}
	return nil
}

// alertStreams format is treeA:streamA,streamB
func writeAlertStreams(c context.Context, alertStreams string) error {
	ds := datastore.Get(c)
	split := strings.Split(alertStreams, ":")
	if len(split) != 2 {
		return fmt.Errorf("invalid alertStreams: %q", alertStreams)
	}

	t := &Tree{Name: split[0]}

	if err := ds.Get(t); err != nil {
		return err
	}

	t.AlertStreams = strings.Split(split[1], ",")
	if err := ds.Put(t); err != nil {
		return err
	}

	return nil
}

// bugQueueLabels format is treeA:queueA,treeB:queueB
func writeBugQueueLabels(c context.Context, bugQueueLabels string) error {
	ds := datastore.Get(c)
	queueLabels := strings.Split(bugQueueLabels, ",")
	for _, label := range queueLabels {
		split := strings.Split(label, ":")
		if len(split) != 2 {
			return fmt.Errorf("invalid bugQueueLabels: %q", bugQueueLabels)
		}

		t := &Tree{Name: split[0]}
		if err := ds.Get(t); err != nil {
			return err
		}

		t.BugQueueLabel = split[1]
		if err := ds.Put(t); err != nil {
			return err
		}
	}

	return nil
}

func (settingsUIPage) WriteSettings(c context.Context, values map[string]string, who, why string) error {
	if treeStr, ok := values["Trees"]; ok {
		if err := writeTrees(c, treeStr); err != nil {
			return err
		}
	}

	if alertStreams, ok := values["AlertStreams"]; ok && alertStreams != "" {
		if err := writeAlertStreams(c, alertStreams); err != nil {
			return err
		}
	}

	if bugQueueLabels, ok := values["BugQueueLabels"]; ok && bugQueueLabels != "" {
		if err := writeBugQueueLabels(c, bugQueueLabels); err != nil {
			return err
		}
	}

	return nil
}

//// Handlers.
func indexPage(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params
	if p.ByName("path") == "" {
		http.Redirect(w, r, "/chromium", http.StatusFound)
		return
	}

	user := auth.CurrentIdentity(c)

	if user.Kind() == identity.Anonymous {
		url, err := auth.LoginURL(c, "/")
		if err != nil {
			errStatus(w, http.StatusInternalServerError, fmt.Sprintf(
				"You must login. Additionally, an error was encountered while serving this request: %s", err.Error()))
		} else {
			http.Redirect(w, r, url, http.StatusFound)
		}

		return
	}

	isGoogler, err := auth.IsMember(c, authGroup)

	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	logoutURL, err := auth.LogoutURL(c, "/")

	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	if !isGoogler {
		err = accessDeniedPage.Execute(w, map[string]interface{}{
			"Group":     authGroup,
			"LogoutURL": logoutURL,
		})
		if err != nil {
			logging.Errorf(c, "while rendering index: %s", err)
		}
		return
	}

	data := map[string]interface{}{
		"User":           user.Email(),
		"LogoutUrl":      logoutURL,
		"IsDevAppServer": appengine.IsDevAppServer(),
	}

	err = mainPage.Execute(w, data)
	if err != nil {
		logging.Errorf(c, "while rendering index: %s", err)
	}
}

func getTreesHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	if !requireGoogler(w, c) {
		return
	}

	q := datastore.NewQuery("Tree")
	results := []*Tree{}
	err := datastore.Get(c).GetAll(q, &results)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	txt, err := json.Marshal(results)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(txt)
}

func getAlertsHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	if !requireGoogler(w, c) {
		return
	}

	ds := datastore.Get(c)

	tree := p.ByName("tree")
	q := datastore.NewQuery("AlertsJSON")
	q = q.Ancestor(ds.MakeKey("Tree", tree))
	q = q.Order("-Date")
	q = q.Limit(1)

	results := []*AlertsJSON{}
	err := ds.GetAll(q, &results)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	if len(results) == 0 {
		logging.Warningf(c, "No alerts found for tree %s", tree)
		errStatus(w, http.StatusNotFound, fmt.Sprintf("Tree \"%s\" not found", tree))
		return
	}

	alertsJSON := results[0]
	w.Header().Set("Content-Type", "application/json")
	w.Write(alertsJSON.Contents)
}

func postAlertsHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	if !requireGoogler(w, c) {
		return
	}

	tree := p.ByName("tree")
	ds := datastore.Get(c)

	alerts := AlertsJSON{
		Tree: ds.MakeKey("Tree", tree),
		Date: clock.Now(c),
	}
	data, err := ioutil.ReadAll(r.Body)
	if err != nil {
		errStatus(w, http.StatusBadRequest, err.Error())
		return
	}

	if err := r.Body.Close(); err != nil {
		errStatus(w, http.StatusBadRequest, err.Error())
		return
	}

	out := make(map[string]interface{})
	err = json.Unmarshal(data, &out)

	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	out["date"] = alerts.Date.String()
	data, err = json.Marshal(out)

	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	alerts.Contents = data
	err = datastore.Get(c).Put(&alerts)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}
}

func getAnnotationsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	if !requireGoogler(w, c) {
		return
	}

	q := datastore.NewQuery("Annotation")
	results := []*Annotation{}
	datastore.Get(c).GetAll(q, &results)

	data, err := json.Marshal(results)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

func postAnnotationsHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	if !requireGoogler(w, c) {
		return
	}

	annKey := p.ByName("annKey")
	action := p.ByName("action")
	ds := datastore.Get(c)

	if !(action == "add" || action == "remove") {
		errStatus(w, http.StatusNotFound, "Invalid action")
		return
	}

	annotation := &Annotation{
		KeyDigest: fmt.Sprintf("%x", sha1.Sum([]byte(annKey))),
		Key:       annKey,
	}

	err := ds.Get(annotation)
	if action == "remove" && err != nil {
		errStatus(w, http.StatusNotFound, fmt.Sprintf("Annotation %s not found", annKey))
		return
	}
	// The annotation probably doesn't exist if we're adding something

	if action == "add" {
		err = annotation.add(c, r.Body)
	} else if action == "remove" {
		err = annotation.remove(c, r.Body)
	}

	if err != nil {
		errStatus(w, http.StatusBadRequest, err.Error())
		return
	}

	err = r.Body.Close()
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	err = ds.Put(annotation)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	data, err := json.Marshal(annotation)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

func getBugQueueHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	// Have to do this because monorail doesn't play nice with the given gae
	// urlfetch stuff already in the context.
	aec := prod.AEContext(c)
	client := &http.Client{
		Transport: &oauth2.Transport{
			Source: google.AppEngineTokenSource(
				aec, "https://www.googleapis.com/auth/userinfo.email"),
			Base: &gaeurlfetch.Transport{
				Context: aec,
			},
		},
	}
	mr := monorail.NewEndpointsClient(client, monorailEndpoint)
	tree := p.ByName("tree")

	// TODO(martiniss): make this look up request info based on Tree datastore
	// object
	req := &monorail.IssuesListRequest{
		ProjectId: "chromium",
		Can:       monorail.IssuesListRequest_OPEN,
		Q:         fmt.Sprintf("label:Sheriff-%s", tree),
	}

	res, err := mr.IssuesList(c, req)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	bytes, err := json.Marshal(res)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(bytes)
}

func getCrRevJSON(c context.Context, pos string) (map[string]string, error) {
	c = client.UseServiceAccountTransport(c, nil, nil)

	hc := &http.Client{Transport: urlfetch.Get(c)}

	resp, err := hc.Get(fmt.Sprintf("https://cr-rev.appspot.com/_ah/api/crrev/v1/redirect/%s", pos))
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	m := map[string]string{}
	err = json.Unmarshal(body, &m)
	if err != nil {
		return nil, err
	}

	return m, nil
}

func getRevRangeHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	start := p.ByName("start")
	end := p.ByName("end")
	if start == "" || end == "" {
		errStatus(w, http.StatusBadRequest, "Start and end parameters must be set.")
		return
	}

	startRev, err := getCrRevJSON(c, start)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	endRev, err := getCrRevJSON(c, end)
	if err != nil {
		errStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	// TODO(seanmccullough): some sanity checking of the rev json (same repo etc)

	gitilesURL := fmt.Sprintf("https://chromium.googlesource.com/chromium/src/+log/%s^..%s?format=JSON",
		startRev["git_sha"], endRev["git_sha"])

	http.Redirect(w, r, gitilesURL, 301)
}

// base is the root of the middleware chain.
func base() router.MiddlewareChain {
	methods := auth.Authenticator{
		&server.OAuth2Method{Scopes: []string{server.EmailScope}},
		server.CookieAuth,
		&server.InboundAppIDAuthMethod{},
	}
	return gaemiddleware.BaseProd().Extend(
		auth.Use(methods),
	)
}

//// Routes.
func init() {

	settings.RegisterUIPage(settingsKey, settingsUIPage{})

	r := router.New()
	basemw := base()
	authmw := basemw.Extend(auth.Authenticate)

	gaemiddleware.InstallHandlers(r, basemw)
	r.GET("/api/v1/trees/", authmw, getTreesHandler)
	r.GET("/api/v1/alerts/:tree", authmw, getAlertsHandler)
	r.POST("/api/v1/alerts/:tree", authmw, postAlertsHandler)
	r.GET("/api/v1/annotations/", authmw, getAnnotationsHandler)
	r.POST("/api/v1/annotations/:annKey/:action", authmw, postAnnotationsHandler)
	r.GET("/api/v1/bugqueue/:tree", authmw, getBugQueueHandler)
	r.GET("/api/v1/revrange/:start/:end", basemw, getRevRangeHandler)

	rootRouter := router.New()
	rootRouter.GET("/*path", authmw, indexPage)

	http.DefaultServeMux.Handle("/api/", r)
	http.DefaultServeMux.Handle("/admin/", r)
	http.DefaultServeMux.Handle("/auth/", r)
	http.DefaultServeMux.Handle("/_ah/", r)
	http.DefaultServeMux.Handle("/internal/", r)

	http.DefaultServeMux.Handle("/", rootRouter)
}
