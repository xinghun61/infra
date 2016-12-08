package analyzer

import (
	"testing"

	"golang.org/x/net/context"

	"infra/monitoring/messages"

	"infra/monitoring/client"
	clientTest "infra/monitoring/client/test"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGetVersionNumber(t *testing.T) {
	Convey("TestGetVersionNumber", t, func() {
		Convey("no configure", func() {
			b := &messages.Build{
				Steps: []messages.Step{
					{
						Name: "foobar",
					},
				},
			}

			_, err := getVersionNumber(b)
			So(err, ShouldNotBeNil)
		})

		Convey("has configure", func() {
			b := &messages.Build{
				Steps: []messages.Step{
					{
						Name: "Configure",
						Text: []string{
							"Version: 22.0.blah",
						},
					},
				},
			}

			version, err := getVersionNumber(b)
			So(err, ShouldBeNil)
			So(version, ShouldEqual, "22.0")
		})
	})
}

func TestOfficialImportantFailures(t *testing.T) {
	Convey("TestOfficialImportantFailures", t, func() {
		mr := &clientTest.MockReader{
			BuildValue: &messages.Build{
				Number: 2,
				Steps: []messages.Step{
					{
						Name: "Configure",
						Text: []string{
							"Version: 22.0.3",
						},
					},
					{
						Results: []interface{}{
							3,
						},
						IsFinished: true,
					},
				},
			},
		}
		a := newTestAnalyzer(0, 10)
		ctx := client.WithReader(context.Background(), mr)

		Convey("basic", func() {
			failures, err := a.officialImportantFailures(ctx, nil, "", []int64{1})
			So(err, ShouldBeNil)
			So(failures, ShouldResemble, []*messages.BuildStep{
				{
					Build: mr.BuildValue,
					Step:  &mr.BuildValue.Steps[len(mr.BuildValue.Steps)-1],
				},
			})

		})
	})
}
