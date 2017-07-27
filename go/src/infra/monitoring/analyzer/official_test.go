package analyzer

import (
	"testing"

	"golang.org/x/net/context"

	"infra/monitoring/messages"

	"infra/monitoring/client"
	clientTest "infra/monitoring/client/test"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGetVersionNumberFromConfigure(t *testing.T) {
	Convey("TestGetVersionNumberFromConfigure", t, func() {
		Convey("no configure", func() {
			b := &messages.Build{
				Steps: []messages.Step{
					{
						Name: "foobar",
					},
				},
			}

			_, err := getVersionNumberFromConfigure(b)
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

			version, err := getVersionNumberFromConfigure(b)
			So(err, ShouldBeNil)
			So(version, ShouldEqual, "22.0")
		})
	})
}

func TestGetVersionNumberFromProperties(t *testing.T) {
	Convey("TestGetVersionNumberFromProperties", t, func() {
		Convey("no configure", func() {
			b := &messages.Build{
				Steps: []messages.Step{
					{
						Name: "foobar",
					},
				},
			}

			_, err := getVersionNumberFromProperties(b)
			So(err, ShouldNotBeNil)
		})

		Convey("has chrome_version property", func() {
			b := &messages.Build{
				Properties: [][]interface{}{
					[]interface{}{"chrome_version", "22.0.blah", "buildbucket"},
				},
			}

			version, err := getVersionNumberFromProperties(b)
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
