// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"infra/monitoring/messages"
	"reflect"
	"strings"
	"testing"
)

func TestCompileFailureAlerts(t *testing.T) {
	tests := []struct {
		name       string
		failure    stepFailure
		stdio      string
		wantResult *StepAnalyzerResult
		wantErr    error
	}{
		{
			name:       "empty",
			wantResult: &StepAnalyzerResult{},
		},
		{
			name: "non-compiler failure",
			failure: stepFailure{
				masterName:  "fake.master",
				builderName: "fake_builder",
				step: messages.Step{
					Name: "tests_compile",
				},
			},
			wantResult: &StepAnalyzerResult{},
		},
		{
			name: "compiler error",
			failure: stepFailure{
				step: messages.Step{
					Name: "compile",
				},
			},
			// Taken from actual stdio logs of a compile failure:
			stdio: `
[4641/28337] CXX obj\third_party\angle\src\libANGLE\libANGLE.Shader.obj
[4642/28337] CXX obj\third_party\angle\src\libANGLE\libANGLE.State.obj
[4643/28337] CXX obj\third_party\angle\src\libANGLE\libANGLE.Surface.obj
[4644/28337] LIB obj\third_party\sqlite\sqlite3.lib
[4645/28337] CXX obj\third_party\angle\src\libANGLE\libANGLE.Texture.obj
[4646/28337] CXX obj\third_party\angle\src\libANGLE\libANGLE.TransformFeedback.obj
[4647/28337] LIB obj\components\cryptauth_test_support.lib
[4648/28337] LINK_EMBED(DLL) base_i18n.dll
FAILED: ninja -t msvc -e environment.x64 -- "..\..\third_party/llvm-build/Release+Asserts/bin/clang-cl" -m64 /nologo /showIncludes /FC @obj\third_party\angle\src\common\libANGLE.event_tracer.obj.rsp /c ..\..\third_party\angle\src\common\event_tracer.cpp /Foobj\third_party\angle\src\common\libANGLE.event_tracer.obj /Fdobj\third_party\angle\src\libANGLE.cc.pdb 
In file included from ..\..\third_party\angle\src\common\event_tracer.cpp:5:
In file included from ..\..\third_party\angle\src\common/event_tracer.h:8:
In file included from ..\..\third_party\angle\src\common/platform.h:61:
C:\b\depot_tools\win_toolchain\vs2013_files\win8sdk/Include/um\d3d11.h(1065,48) :  error: default initialization of an object of const type 'const CD3D11_DEFAULT' without a user-provided default constructor
extern const DECLSPEC_SELECTANY CD3D11_DEFAULT D3D11_DEFAULT;
                                               ^
C:\b\depot_tools\win_toolchain\vs2013_files\win8sdk/Include/um\d3d11.h(1065,61) :  note: add an explicit initializer to initialize 'D3D11_DEFAULT'
extern const DECLSPEC_SELECTANY CD3D11_DEFAULT D3D11_DEFAULT;
                                                            ^
C:\b\depot_tools\win_toolchain\vs2013_files\win8sdk/Include/um\d3d11.h(9570,54) :  error: default initialization of an object of const type 'const CD3D11_VIDEO_DEFAULT' without a user-provided default constructor
extern const DECLSPEC_SELECTANY CD3D11_VIDEO_DEFAULT D3D11_VIDEO_DEFAULT;
                                                     ^
C:\b\depot_tools\win_toolchain\vs2013_files\win8sdk/Include/um\d3d11.h(9570,73) :  note: add an explicit initializer to initialize 'D3D11_VIDEO_DEFAULT'
extern const DECLSPEC_SELECTANY CD3D11_VIDEO_DEFAULT D3D11_VIDEO_DEFAULT;
                                                                        ^
2 errors generated.
`,
			wantResult: &StepAnalyzerResult{
				Reasons: []string{
					`C:\b\depot_tools\win_toolchain\vs2013_files\win8sdk/Include/um\d3d11.h:1065`,
					`C:\b\depot_tools\win_toolchain\vs2013_files\win8sdk/Include/um\d3d11.h:9570`,
				},
				Recognized: true,
			},
		},
	}

	mc := &mockClient{}
	a := &CompileFailureAnalyzer{mc}

	for _, test := range tests {
		mc.stdioForStep = strings.Split(test.stdio, "\n")
		gotResult, gotErr := a.Analyze(test.failure)
		if !reflect.DeepEqual(gotResult, test.wantResult) {
			t.Errorf("%s failed.\n\tGot:\n\t%+v\n\twant:\n\t%+v.", test.name, gotResult, test.wantResult)
		}
		if !reflect.DeepEqual(gotErr, test.wantErr) {
			t.Errorf("%s failed. Got: %+v want: %+v.", test.name, gotErr, test.wantErr)
		}
	}
}
