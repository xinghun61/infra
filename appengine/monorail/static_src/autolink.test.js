import {assert} from 'chai';
import {autolink} from './autolink.js';

const components = autolink.Components;
const markupAutolinks = autolink.markupAutolinks;

describe('autolink', () => {
  describe('crbug component functions', () => {
    const {extractRefs, refRegs, replacer} = components.get('01-tracker-crbug');

    it('Extract crbug project and local ids', () => {
      const match = refRegs[0].exec('https://crbug.com/monorail/1234');
      refRegs[0].lastIndex = 0;
      const ref = extractRefs(match);
      assert.deepEqual(ref, [{projectName: 'monorail', localId: '1234'}]);
    });

    it('Extract crbug default project name', () => {
      const match = refRegs[0].exec('http://crbug.com/1234');
      refRegs[0].lastIndex = 0;
      const ref = extractRefs(match);
      assert.deepEqual(ref, [{projectName: 'chromium', localId: '1234'}]);
    });

    it('Extract crbug passed project name is ignored', () => {
      const match = refRegs[0].exec('https://crbug.com/1234');
      refRegs[0].lastIndex = 0;
      const ref = extractRefs(match, 'foo');
      assert.deepEqual(ref, [{projectName: 'chromium', localId: '1234'}]);
    });

    it('Replace crbug with found components', () => {
      const str = 'crbug.com/monorail/1234';
      const match = refRegs[0].exec(str);
      refRegs[0].lastIndex = 0;
      const components = {
        closedRefs: [
          {summary: 'Issue summary', localId: 1234, projectName: 'monorail'},
          {},
        ]};
      const actualRun = replacer(match, components);
      assert.deepEqual(
        actualRun,
        [{
          tag: 'a',
          css: 'strike-through',
          href: '/p/monorail/issues/detail?id=1234',
          title: 'Issue summary',
          content: str,
        }]
      );
    });

    it('Replace crbug with found components, with comment', () => {
      const str = 'crbug.com/monorail/1234#c1';
      const match = refRegs[0].exec(str);
      refRegs[0].lastIndex = 0;
      const components = {
        closedRefs: [
          {summary: 'Issue summary', localId: 1234, projectName: 'monorail'},
          {},
        ]};
      const actualRun = replacer(match, components);
      assert.deepEqual(
        actualRun,
        [{
          tag: 'a',
          css: 'strike-through',
          href: '/p/monorail/issues/detail?id=1234#c1',
          title: 'Issue summary',
          content: str,
        }]
      );
    });

    it('Replace crbug with default project_name', () => {
      const str = 'crbug.com/1234';
      const match = refRegs[0].exec(str);
      refRegs[0].lastIndex = 0;
      const components = {
        openRefs: [
          {localId: 134},
          {summary: 'Issue 1234', localId: 1234, projectName: 'chromium'},
        ],
      };
      const actualRun = replacer(match, components);
      assert.deepEqual(
        actualRun,
        [{
          tag: 'a',
          href: '/p/chromium/issues/detail?id=1234',
          css: '',
          title: 'Issue 1234',
          content: str,
        }]
      );
    });

    it('Replace crbug incomplete responses', () => {
      const str = 'crbug.com/1234';
      const match = refRegs[0].exec(str);
      refRegs[0].lastIndex = 0;
      const components = {
        openRefs: [{localId: 1234}, {projectName: 'chromium'}],
        closedRefs: [{localId: 1234}, {projectName: 'chromium'}],
      };
      const actualRun = replacer(match, components);
      assert.deepEqual(actualRun, [{content: str}]);
    });

    it('Replace crbug passed project name is ignored', () => {
      const str = 'crbug.com/1234';
      const match = refRegs[0].exec(str);
      refRegs[0].lastIndex = 0;
      const components = {
        openRefs: [
          {localId: 134},
          {summary: 'Issue 1234', localId: 1234, projectName: 'chromium'},
        ],
      };
      const actualRun = replacer(match, components, 'foo');
      assert.deepEqual(
        actualRun,
        [{
          tag: 'a',
          href: '/p/chromium/issues/detail?id=1234',
          css: '',
          title: 'Issue 1234',
          content: str,
        }]
      );
    });

    it('Replace crbug with no found components', () => {
      const str = 'crbug.com/1234';
      const match = refRegs[0].exec(str);
      refRegs[0].lastIndex = 0;
      const components = {};
      const actualRun = replacer(match, components);
      assert.deepEqual(actualRun, [{content: str}]);
    });

    it('Replace crbug with no issue summary', () => {
      const str = 'crbug.com/monorail/1234';
      const match = refRegs[0].exec(str);
      refRegs[0].lastIndex = 0;
      const components = {
        closedRefs: [
          {localId: 1234, projectName: 'monorail'},
          {},
        ]};
      const actualRun = replacer(match, components);
      assert.deepEqual(
        actualRun,
        [{
          tag: 'a',
          css: 'strike-through',
          href: '/p/monorail/issues/detail?id=1234',
          title: '',
          content: str,
        }]
      );
    });
  });

  describe('regular tracker component functions', () => {
    const {extractRefs, refRegs, replacer} =
      components.get('04-tracker-regular');
    const str = 'bugs=123, monorail:234 or #345 and PROJ:#456';
    const match = refRegs[0].exec(str);
    refRegs[0].lastIndex = 0;

    it('Extract tracker projects and local ids', () => {
      const actualRefs = extractRefs(match, 'foo-project');
      assert.deepEqual(
        actualRefs,
        [{projectName: 'foo-project', localId: '123'},
          {projectName: 'monorail', localId: '234'},
          {projectName: 'monorail', localId: '345'},
          {projectName: 'PROJ', localId: '456'}]);
    });

    it('Replace tracker refs.', () => {
      const components = {
        openRefs: [
          {summary: 'sum', projectName: 'monorail', localId: 888},
          {summary: 'ma', projectName: 'chromium', localId: '123'},
        ],
        closedRefs: [
          {summary: 'ry', projectName: 'proj', localId: 456},
        ],
      };
      const actualTextRuns = replacer(match, components, 'chromium');
      assert.deepEqual(
        actualTextRuns,
        [
          {content: 'bugs='},
          {
            tag: 'a',
            href: '/p/chromium/issues/detail?id=123',
            css: '',
            title: 'ma',
            content: '123',
          },
          {content: ', '},
          {content: 'monorail:234'},
          {content: ' or '},
          {content: '#345'},
          {content: ' and '},
          {
            tag: 'a',
            href: '/p/PROJ/issues/detail?id=456',
            css: 'strike-through',
            title: 'ry',
            content: 'PROJ:#456',
          },
        ]
      );
    });

    it('Replace tracker refs mixed case refs.', () => {
      const components = {
        openRefs: [
          {projectName: 'mOnOrAIl', localId: 234},
        ],
        closedRefs: [
          {projectName: 'LeMuR', localId: 123},
        ],
      };
      const actualTextRuns = replacer(match, components, 'lEmUr');
      assert.deepEqual(
        actualTextRuns,
        [
          {content: 'bugs='},
          {
            tag: 'a',
            href: '/p/lEmUr/issues/detail?id=123',
            css: 'strike-through',
            title: '',
            content: '123',
          },
          {content: ', '},
          {
            tag: 'a',
            href: '/p/monorail/issues/detail?id=234',
            css: '',
            title: '',
            content: 'monorail:234',
          },
          {content: ' or '},
          {content: '#345'},
          {content: ' and '},
          {content: 'PROJ:#456'},
        ],
      );
    });
  });

  describe('user email component functions', () => {
    const {extractRefs, refRegs, replacer} = components.get('03-user-emails');
    const str = 'We should ask User1@gmail.com to confirm.';
    const match = refRegs[0].exec(str);
    refRegs[0].lastIndex = 0;

    it('Extract user email', () => {
      const actualEmail = extractRefs(match, 'unusedProjectName');
      assert.equal('User1@gmail.com', actualEmail);
    });

    it('Replace existing user.', () => {
      const components = {
        users: [{email: 'user2@gmail.com'}, {email: 'user1@gmail.com'}]};
      const actualTextRun = replacer(match, components);
      assert.deepEqual(
        actualTextRun,
        [{tag: 'a', href: '/u/User1@gmail.com', content: 'User1@gmail.com'}]
      );
    });

    it('Replace non-existent user.', () => {
      const actualTextRun = replacer(match, {});
      assert.deepEqual(
        actualTextRun,
        [{
          tag: 'a',
          href: 'mailto:User1@gmail.com',
          content: 'User1@gmail.com',
        }]
      );
    });
  });

  describe('full url component functions.', () => {
    const {refRegs, replacer} = components.get('02-full-urls');

    it('test full link regex string', () => {
      const isLinkRE = refRegs[0];
      const str =
        'https://www.go.com ' +
        'nospacehttps://www.blah.com http://website.net/other="(}])"><)';
      let match;
      const actualMatches = [];
      while ((match = isLinkRE.exec(str)) !== null) {
        actualMatches.push(match[0]);
      }
      assert.deepEqual(
        actualMatches,
        ['https://www.go.com', 'http://website.net/other="(}])">']);
    });

    it('Replace URL existing http', () => {
      const match = refRegs[0].exec('link here: (https://website.net/other="here").');
      refRegs[0].lastIndex = 0;
      const actualTextRuns = replacer(match);
      assert.deepEqual(
        actualTextRuns,
        [{tag: 'a',
          href: 'https://website.net/other="here"',
          content: 'https://website.net/other="here"',
        },
        {content: ').'}]
      );
    });

    it('Replace URL with short-link as substring', () => {
      const match = refRegs[0].exec('https://website.net/who/me/yes/you');
      refRegs[0].lastIndex = 0;
      const actualTextRuns = replacer(match);

      assert.deepEqual(
        actualTextRuns,
        [{tag: 'a',
          href: 'https://website.net/who/me/yes/you',
          content: 'https://website.net/who/me/yes/you',
        }]
      );
    });

    it('Replace URL with email as substring', () => {
      const match = refRegs[0].exec('https://website.net/who/foo@example.com');
      refRegs[0].lastIndex = 0;
      const actualTextRuns = replacer(match);

      assert.deepEqual(
        actualTextRuns,
        [{tag: 'a',
          href: 'https://website.net/who/foo@example.com',
          content: 'https://website.net/who/foo@example.com',
        }]
      );
    });
  });

  describe('shorthand url component functions.', () => {
    const {refRegs, replacer} = components.get('05-linkify-shorthand');

    it('Short link does not match URL with short-link as substring', () => {
      refRegs[0].lastIndex = 0;
      assert.isNull(refRegs[0].exec('https://website.net/who/me/yes/you'));
    });

    it('test short link regex string', () => {
      const shortLinkRE = refRegs[0];
      const str =
        'go/shortlinks ./_go/shortlinks bo/short bo/1234  ' +
        'https://who/shortlinks go/hey/?wct=(go)';
      let match;
      let actualMatches = [];
      while ((match = shortLinkRE.exec(str)) !== null) {
        actualMatches.push(match[0]);
      }
      assert.deepEqual(
        actualMatches,
        ['go/shortlinks', ' https://who/shortlinks', ' go/hey/?wct=(go)']
      );
    });

    it('test numeric short link regex string', () => {
      const shortNumLinkRE = refRegs[1];
      const str = 'go/nono omg/ohno omg/123 .cl/123 b/1234';
      let match;
      let actualMatches = [];
      while ((match = shortNumLinkRE.exec(str)) !== null) {
        actualMatches.push(match[0]);
      }
      assert.deepEqual(actualMatches, [' omg/123', ' b/1234']);
    });

    it('test implied link regex string', () => {
      const impliedLinkRE = refRegs[2];
      const str = 'incomplete.com .help.com hey.net/other="(blah)"';
      let match;
      let actualMatches = [];
      while ((match = impliedLinkRE.exec(str)) !== null) {
        actualMatches.push(match[0]);
      }
      assert.deepEqual(
        actualMatches, ['incomplete.com', ' hey.net/other="(blah)"']);
    });

    it('Replace URL plain text', () => {
      const match = refRegs[2].exec('link here: (website.net/other="here").');
      refRegs[2].lastIndex = 0;
      const actualTextRuns = replacer(match);
      assert.deepEqual(
        actualTextRuns,
        [{content: '('},
          {tag: 'a',
            href: 'https://website.net/other="here"',
            content: 'website.net/other="here"',
          },
          {content: ').'}]
      );
    });

    it('Replace short link existing http', () => {
      const match = refRegs[0].exec('link here: (http://who/me).');
      refRegs[0].lastIndex = 0;
      const actualTextRuns = replacer(match);
      assert.deepEqual(
        actualTextRuns,
        [{content: '('},
          {tag: 'a',
            href: 'http://who/me',
            content: 'http://who/me',
          },
          {content: ').'}]
      );
    });

    it('Replace short-link plain text', () => {
      const match = refRegs[0].exec('link here: (who/me).');
      refRegs[0].lastIndex = 0;
      const actualTextRuns = replacer(match);
      assert.deepEqual(
        actualTextRuns,
        [{content: '('},
          {tag: 'a',
            href: 'http://who/me',
            content: 'who/me',
          },
          {content: ').'}]
      );
    });

    it('Replace short-link plain text initial characters', () => {
      const match = refRegs[0].exec('link here: who/me');
      refRegs[0].lastIndex = 0;
      const actualTextRuns = replacer(match);
      assert.deepEqual(
        actualTextRuns,
        [{content: ' '},
          {tag: 'a',
            href: 'http://who/me',
            content: 'who/me',
          }]
      );
    });

    it('Replace URL short link', () => {
      ['go', 'g', 'shortn', 'who', 'teams'].forEach((prefix) => {
        const match = refRegs[0].exec(`link here: (${prefix}/abcd).`);
        refRegs[0].lastIndex = 0;
        const actualTextRuns = replacer(match);
        assert.deepEqual(
          actualTextRuns,
          [{content: '('},
            {tag: 'a',
              href: `http://${prefix}/abcd`,
              content: `${prefix}/abcd`,
            },
            {content: ').'}]
        );
      });
    });

    it('Replace URL numeric short link', () => {
      ['b', 't', 'o', 'omg', 'cl', 'cr'].forEach((prefix) => {
        const match = refRegs[1].exec(`link here: (${prefix}/1234).`);
        refRegs[1].lastIndex = 0;
        const actualTextRuns = replacer(match);
        assert.deepEqual(
          actualTextRuns,
          [{content: '('},
            {tag: 'a',
              href: `http://${prefix}/1234`,
              content: `${prefix}/1234`,
            }]
        );
      });
    });
  });

  describe('versioncontrol component functions.', () => {
    const {refRegs, replacer} = components.get('06-versioncontrol');

    it('test git hash regex', () => {
      const gitHashRE = refRegs[0];
      const str =
          'r63b72a71d5fbce6739c51c3846dd94bd62b91091 blha blah ' +
          'Revision 63b72a71d5fbce6739c51c3846dd94bd62b91091 blah balh ' +
          '63b72a71d5fbce6739c51c3846dd94bd62b91091 ' +
          'Revision63b72a71d5fbce6739c51c3846dd94bd62b91091';
      let match;
      const actualMatches = [];
      while ((match = gitHashRE.exec(str)) !== null) {
        actualMatches.push(match[0]);
      }
      assert.deepEqual(
        actualMatches, [
          'r63b72a71d5fbce6739c51c3846dd94bd62b91091',
          'Revision 63b72a71d5fbce6739c51c3846dd94bd62b91091',
          '63b72a71d5fbce6739c51c3846dd94bd62b91091',
        ]);
    });

    it('test svn regex', () => {
      const svnRE = refRegs[1];
      const str =
          'r1234 blah blah ' +
          'Revision 123456 blah balh ' +
          'r12345678' +
          '1234';
      let match;
      const actualMatches = [];
      while ((match = svnRE.exec(str)) !== null) {
        actualMatches.push(match[0]);
      }
      assert.deepEqual(
        actualMatches, [
          'r1234',
          'Revision 123456',
        ]);
    });

    it('replace revision refs plain text', () => {
      const str = 'r63b72a71d5fbce6739c51c3846dd94bd62b91091';
      const match = refRegs[0].exec(str);
      const actualTextRuns = replacer(match);
      refRegs[0].lastIndex = 0;
      assert.deepEqual(
        actualTextRuns,
        [{
          content: 'r63b72a71d5fbce6739c51c3846dd94bd62b91091',
          tag: 'a',
          href: 'https://crrev.com/63b72a71d5fbce6739c51c3846dd94bd62b91091',
        }]);
    });
  });


  describe('markupAutolinks tests', () => {
    const componentRefs = new Map();
    componentRefs.set('01-tracker-crbug', {
      openRefs: [],
      closedRefs: [{projectName: 'chromium', localId: 99}],
    });
    componentRefs.set('04-tracker-regular', {
      openRefs: [{summary: 'monorail', projectName: 'monorail', localId: 123}],
      closedRefs: [{projectName: 'chromium', localId: 456}],
    });
    componentRefs.set('03-user-emails', {
      users: [{email: 'user2@example.com'}],
    });

    it('empty string does not cause error', () => {
      const actualTextRuns = markupAutolinks('', componentRefs);
      assert.deepEqual(actualTextRuns, []);
    });

    it('no nested autolinking', () => {
      const plainString = 'test <b>autolinking go/testlink</b> is not nested';
      const actualTextRuns = markupAutolinks(plainString, componentRefs);
      assert.deepEqual(
        actualTextRuns, [
          {content: 'test '},
          {content: 'autolinking go/testlink', tag: 'b'},
          {content: ' is not nested'},
        ]);
    });

    it('URLs are autolinked', () => {
      const plainString = 'this http string contains http://google.com for you';
      const actualTextRuns = markupAutolinks(plainString, componentRefs);
      assert.deepEqual(
        actualTextRuns, [
          {content: 'this http string contains '},
          {content: 'http://google.com', tag: 'a', href: 'http://google.com'},
          {content: ' for you'},
        ]);
    });

    it('different component types are correctly linked', () => {
      const plainString = 'test (User2@example.com and crbug.com/99) get link';
      const actualTextRuns = markupAutolinks(plainString, componentRefs);
      assert.deepEqual(
        actualTextRuns,
        [
          {
            content: 'test (',
          },
          {
            content: 'User2@example.com',
            tag: 'a',
            href: '/u/User2@example.com',
          },
          {
            content: ' and ',
          },
          {
            content: 'crbug.com/99',
            tag: 'a',
            href: '/p/chromium/issues/detail?id=99',
            title: '',
            css: 'strike-through',
          },
          {
            content: ') get link',
          },
        ]
      );
    });

    it('Invalid issue refs do not get linked', () => {
      const plainString =
        'bug123, bug 123a, bug-123 and https://bug:123.example.com ' +
        'do not get linked.';
      const actualTextRuns= markupAutolinks(
        plainString, componentRefs, 'chromium');
      assert.deepEqual(
        actualTextRuns,
        [
          {
            content: 'bug123, bug 123a, bug-123 and ',
          },
          {
            content: 'https://bug:123.example.com',
            tag: 'a',
            href: 'https://bug:123.example.com',
          },
          {
            content: ' do not get linked.',
          },
        ]);
    });

    it('Only existing issues get linked', () => {
      const plainString =
        'only existing bugs = 456, monorail:123, 234 and chromium:345 get ' +
        'linked';
      const actualTextRuns = markupAutolinks(
        plainString, componentRefs, 'chromium');
      assert.deepEqual(
        actualTextRuns,
        [
          {
            content: 'only existing ',
          },
          {
            content: 'bugs = ',
          },
          {
            content: '456',
            tag: 'a',
            href: '/p/chromium/issues/detail?id=456',
            title: '',
            css: 'strike-through',
          },
          {
            content: ', ',
          },
          {
            content: 'monorail:123',
            tag: 'a',
            href: '/p/monorail/issues/detail?id=123',
            title: 'monorail',
            css: '',
          },
          {
            content: ', ',
          },
          {
            content: '234',
          },
          {
            content: ' and ',
          },
          {
            content: 'chromium:345',
          },
          {
            content: ' ',
          },
          {
            content: 'get linked',
          },
        ]
      );
    });

    it('multilined bolds are not bolded', () => {
      const plainString =
        '<b>no multiline bolding \n' +
        'not allowed go/survey is still linked</b>';
      const actualTextRuns = markupAutolinks(plainString, componentRefs);
      assert.deepEqual(
        actualTextRuns, [
          {content: '<b>no multiline bolding '},
          {tag: 'br'},
          {content: 'not allowed'},
          {content: ' '},
          {content: 'go/survey', tag: 'a', href: 'http://go/survey'},
          {content: ' is still linked</b>'},
        ]);

      const plainString2 =
        '<b>no multiline bold \rwith carriage \r\nreturns</b>';
      const actualTextRuns2 = markupAutolinks(plainString2, componentRefs);

      assert.deepEqual(
        actualTextRuns2, [
          {content: '<b>no multiline bold '},
          {tag: 'br'},
          {content: 'with carriage '},
          {tag: 'br'},
          {content: 'returns</b>'},
        ]);
    });

    // Test to check that comment references are properly linked.
    it('comments are correctly linked', () => {
      const plainString =
      'comment1, comment : 5, Comment =10, comment #4, #c57';
      const actualTextRuns = markupAutolinks(plainString, componentRefs);
      console.log(actualTextRuns);
      assert.deepEqual(
        actualTextRuns, [
          {
            content: 'comment1',
            tag: 'a',
            href: '#c1',
          },
          {
            content: ', ',
          },
          {
            content: 'comment : 5',
            tag: 'a',
            href: '#c5',
          },
          {
            content: ', ',
          },
          {
            content: 'Comment =10',
            tag: 'a',
            href: '#c10',
          },
          {
            content: ', ',
          },
          {
            content: 'comment #4',
            tag: 'a',
            href: '#c4',
          },
          {
            content: ', ',
          },
          {
            content: '#c57',
            tag: 'a',
            href: '#c57',
          },
        ]
      );
    });

    // Check that improperly formatted comment references do not get linked.
    it('comments that should not be linked', () => {
      const plainString =
      'comment number 4, comment-4, comment= # 5, comment#c56';
      const actualTextRuns = markupAutolinks(plainString, componentRefs);
      assert.deepEqual(
        actualTextRuns, [
          {
            content: 'comment number 4, comment-4, comment= # 5, comment#c56',
          },
        ]
      );
    });
  });
});
