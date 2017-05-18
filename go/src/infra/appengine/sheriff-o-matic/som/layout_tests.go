package som

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"time"

	"golang.org/x/net/context"

	te "infra/libs/testexpectations"

	"github.com/luci/luci-go/server/router"
)

type shortExp struct {
	FileName     string
	LineNumber   int
	TestName     string
	Bugs         []string
	Modifiers    []string
	Expectations []string
}

type byTestName []*shortExp

func (a byTestName) Len() int           { return len(a) }
func (a byTestName) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a byTestName) Less(i, j int) bool { return a[i].TestName < a[j].TestName }

func getLayoutTestsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer
	c, cancelFunc := context.WithTimeout(c, 60*time.Second)
	defer cancelFunc()

	fs, err := te.LoadAll(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	res := []*shortExp{}
	for _, f := range fs.Files {
		for _, e := range f.Expectations {
			if e.TestName != "" {
				res = append(res, &shortExp{
					FileName:     f.Path,
					LineNumber:   e.LineNumber + 1,
					Bugs:         e.Bugs,
					TestName:     e.TestName,
					Modifiers:    e.Modifiers,
					Expectations: e.Expectations,
				})
			}
		}
	}

	sort.Sort(byTestName(res))

	b, err := json.Marshal(res)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	fmt.Fprintf(w, "%v\n", string(b))
}
