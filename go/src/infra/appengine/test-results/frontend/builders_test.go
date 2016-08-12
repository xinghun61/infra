package frontend

import (
	"infra/appengine/test-results/buildextract"
	"infra/appengine/test-results/masters"
	"net/http"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestBuilders(t *testing.T) {
	Convey("builders", t, func() {
		Convey("getBuilderData", func() {
			Convey("normal", func() {
				tClient := &buildextract.TestingClient{
					M: map[string][]byte{
						"chromium.webkit": []byte(`{
								"builders": {
									"WebKit Win": null,
									"WebKit Linux": null,
									"WebKit Mac": null,
									"WebKit Empty": null
								}
							}`),
					},
					B: map[string]map[string][]byte{
						"chromium.webkit": {
							"WebKit Linux": []byte(`{
								"builds": [
									{
										"steps": [
											{"name": "foo_tests_only"},
											{"name": "webkit_tests"},
											{"name": "browser_tests"},
											{"name": "mini_installer_test"},
											{"name": "archive_test_results"},
											{"name": "duplicate_builders_test"},
											{"name": "duplicate_builders_test"},
											{"name": "compile"},
											{"name": "Upload to test-results [swarming_gtest_tests]"}
										]
									}
								]
							}`),
							"WebKit Win": []byte(`{
								"builds": [
									{
										"steps": [
											{"name": "foo_tests_ignore"},
											{"name": "webkit_tests"},
											{"name": "mini_installer_test"},
											{"name": "archive_test_results"},
											{"name": "compile"}
										]
									}
								]
							}`),
							"WebKit Mac": []byte(`{
								"builds": [
									{
										"steps": [
											{"name": "foo_tests_perf"},
											{"name": "browser_tests"},
											{"name": "mini_installer_test"},
											{"name": "archive_test_results"},
											{"name": "compile"}
										]
									}
								]
							}`),
							"WebKit Empty": []byte(`{
								"builds": []
							}`),
						},
					},
				}

				expected := BuilderData{
					Masters: []Master{{
						Tests: map[string]Test{
							"browser_tests":           {Builders: []string{"WebKit Linux", "WebKit Mac"}},
							"mini_installer_test":     {Builders: []string{"WebKit Linux", "WebKit Mac", "WebKit Win"}},
							"webkit_tests":            {Builders: []string{"WebKit Linux", "WebKit Win"}},
							"swarming_gtest_tests":    {Builders: []string{"WebKit Linux"}},
							"duplicate_builders_test": {Builders: []string{"WebKit Linux"}},
						},
						Identifier: "chromium.webkit",
						Name:       "ChromiumWebKit",
						Groups:     []string{"@ToT Chromium", "@ToT Blink"},
					}},
					NoUploadTestTypes: noUploadTestSteps,
				}

				data, err := getBuilderData(context.Background(), []*masters.Master{{
					Identifier: "chromium.webkit",
					Name:       "ChromiumWebKit",
					Groups:     []string{"@ToT Chromium", "@ToT Blink"},
				}}, tClient)

				So(err, ShouldBeNil)
				So(data, ShouldResemble, expected)
			})

			Convey("error handling", func() {
				tClient := &buildextract.TestingClient{
					M: map[string][]byte{
						"chromium.gpu": []byte(`{
							"builders": {
								"Win GPU": null,
								"Win Empty": null
							}
						}`),
					},
					B: map[string]map[string][]byte{
						"chromium.gpu": {
							"Win Empty": []byte(`{
								"builds": [
									{ "steps": [] }
								]
							}`),
							"Win GPU": []byte(`{
								"builds": [
									{ "steps": [] }
								]
							}`),
						},
					},
				}

				_, err := getBuilderData(context.Background(), []*masters.Master{{
					Identifier: "chromium.webkit",
					Name:       "ChromiumWebKit",
				}}, tClient)
				So(err, ShouldHaveSameTypeAs, &buildextract.StatusError{})
				So(err.(*buildextract.StatusError).StatusCode, ShouldEqual, http.StatusNotFound)

				_, err = getBuilderData(context.Background(), []*masters.Master{{
					Identifier: "chromium.gpu",
					Name:       "ChromiumGPU",
				}}, tClient)
				So(err, ShouldBeNil)
			})
		})
	})
}
