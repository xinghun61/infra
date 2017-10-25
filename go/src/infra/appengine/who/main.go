package who

import (
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/auth/identity"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
)

const (
	authGroup = "chromium-who-access"
)

var (
	mainPage         = template.Must(template.ParseFiles("./index.html"))
	accessDeniedPage = template.Must(template.ParseFiles("./access-denied.html"))
)

func base(includeCookie bool) router.MiddlewareChain {
	a := auth.Authenticator{
		Methods: []auth.Method{
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
			&server.InboundAppIDAuthMethod{},
		},
	}
	if includeCookie {
		a.Methods = append(a.Methods, server.CookieAuth)
	}
	return standard.Base().Extend(a.GetMiddleware())
}

var errStatus = func(c context.Context, w http.ResponseWriter, status int, msg string) {
	logging.Errorf(c, "Status %d msg %s", status, msg)
	w.WriteHeader(status)
	w.Write([]byte(msg))
}

func requireGoogler(c *router.Context, next router.Handler) {
	isGoogler, err := auth.IsMember(c.Context, authGroup)
	switch {
	case err != nil:
		errStatus(c.Context, c.Writer, http.StatusInternalServerError, err.Error())
	case !isGoogler:
		errStatus(c.Context, c.Writer, http.StatusForbidden, "Access denied")
	default:
		next(c)
	}
}

func indexPage(ctx *router.Context) {
	c, w, r, _ := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	user := auth.CurrentIdentity(c)

	if user.Kind() == identity.Anonymous {
		url, err := auth.LoginURL(c, "/")
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf(
				"You must login. Additionally, an error was encountered while serving this request: %s", err.Error()))
		} else {
			http.Redirect(w, r, url, http.StatusFound)
		}

		return
	}

	isGoogler, err := auth.IsMember(c, authGroup)

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	logoutURL, err := auth.LogoutURL(c, "/")

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	data := map[string]string{
		"User":      user.Email(),
		"LogoutUrl": logoutURL,
	}

	if !isGoogler {
		err = accessDeniedPage.Execute(w, data)
		if err != nil {
			logging.Errorf(c, "while rendering index: %s", err)
		}
		return
	}

	err = mainPage.Execute(w, data)
	if err != nil {
		logging.Errorf(c, "while rendering index: %s", err)
	}
}

// Bug is a dummy struct. Put whatever you want in here, I'll hook it up
// to the actual api in a follow-up CL.
type Bug struct {
	ID, Title, Status string
	LastUpdate        time.Time
}

// Change is a dummy struct. Put whatever you want in here, I'll hook it up
// to the actual api in a follow-up CL.
type Change struct {
	ID, Title, Status string
	LastUpdate        time.Time
}

// DayDetails is a list of activity for a user on a given day.
type DayDetails struct {
	Username string
	Bugs     []Bug
	Changes  []Change
}

// ActivityCounts contains counts for user activities on a given day.
type ActivityCounts struct {
	Changes, Bugs int
	Day           time.Time
}

// ActivityHistory holds daily activity counts for a user over some data range.
type ActivityHistory struct {
	Activities []ActivityCounts
}

func historyHandler(ctx *router.Context) {
	c, w, _, _ := ctx.Context, ctx.Writer, ctx.Request, ctx.Params
	encoder := json.NewEncoder(w)

	h := ActivityHistory{
		Activities: []ActivityCounts{},
	}

	now := time.Now()
	for i := 0; i < 28; i++ {
		a := ActivityCounts{
			Bugs:    i,
			Changes: i,
			Day:     now.Add(time.Duration(-i*24) * time.Hour),
		}

		h.Activities = append(h.Activities, a)
	}

	if err := encoder.Encode(h); err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error json encoding: %v", err))
	}
}

func detailHandler(ctx *router.Context) {
	c, w, _, _ := ctx.Context, ctx.Writer, ctx.Request, ctx.Params
	encoder := json.NewEncoder(w)

	if err := encoder.Encode(DayDetails{
		Bugs: []Bug{
			{"1", "dummy bug", "Open", time.Now()},
			{"2", "another dummy bug", "Open", time.Now()},
		},
		Changes: []Change{
			{"1", "dummy change", "Open", time.Now()},
			{"2", "another dummy change", "Open", time.Now()},
		},
	}); err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error json encoding: %v", err))
	}
}

func init() {
	r := router.New()
	basemw := base(true)
	protected := basemw.Extend(requireGoogler)
	standard.InstallHandlers(r)

	r.GET("/", basemw, indexPage)
	r.GET("/_/history", protected, historyHandler)
	r.GET("/_/detail", protected, detailHandler)

	http.DefaultServeMux.Handle("/_/", r)
	http.DefaultServeMux.Handle("/_ah/", r)
	http.DefaultServeMux.Handle("/auth/", r)
	http.DefaultServeMux.Handle("/admin/", r)
	http.DefaultServeMux.Handle("/", r)
}
