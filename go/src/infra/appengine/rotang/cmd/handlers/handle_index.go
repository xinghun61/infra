package handlers

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/datastore"
	"net/http"

	"go.chromium.org/gae/service/user"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// HandleIndex is the handler used for requests to '/'.
func (h *State) HandleIndex(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	rds, err := datastore.New(ctx.Context)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	var ds rotang.ConfigStorer = rds

	res := []struct {
		Rota string
	}{}

	usr := user.Current(ctx.Context)
	if usr != nil {
		rotas, err := ds.MemberOf(ctx.Context, usr.Email)
		if err != nil && status.Code(err) != codes.NotFound {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}

		for _, rota := range rotas {
			res = append(res, struct {
				Rota string
			}{
				Rota: rota,
			})
		}
	}
	templates.MustRender(ctx.Context, ctx.Writer, "pages/index.html", templates.Args{"Rotas": res, "User": usr})
}
