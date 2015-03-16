module('builderstate');

test('loading', 5, function() {
  var oldDate = Date;
  Date = function(timestamp) {
    this._date = new oldDate(timestamp);
  };

  Date.now = function() {
    return Date._now;
  };

  Date.parse = oldDate.parse;

  Date.prototype.toISOString = function() {
    return this._date.toISOString();
  };

  var blankData = {};
  var html = builderstate.generateHtml(blankData);
  equal('', html);

  var oneMaster = {
    masters: [
      {
        name: 'a master',
        tests: {
          'a test': {
             builders: {
               'a builder': '2015-02-11T23:39:20.033790'
             }
          }
        }
      }
    ]
  };

  Date._now = oldDate.parse('2015-02-11T23:39:20.033790');

  html = builderstate.generateHtml(oneMaster);

  equal(html, `
          <tr>
            <td>a test</td>
            <td>
               a master:a builder
               [<a href="http://test-results.appspot.com/testfile?testtype=a%20test&builder=a%20builder&master=undefined" target="_blank">results</a>] [<a href="http://build.chromium.org/p/undefined/builders/a%20builder" target="_blank">builder</a>]
            </td>
            <td class="">2015-02-11T23:39:20.033790 (00:00:00)</td>
          </tr>
        `);

  // Fast forward a few days, minutes.
  Date._now = oldDate.parse('2015-02-15T23:59:20.033790');

  html = builderstate.generateHtml(oneMaster);

  equal(html, `
          <tr>
            <td>a test</td>
            <td>
               a master:a builder
               [<a href="http://test-results.appspot.com/testfile?testtype=a%20test&builder=a%20builder&master=undefined" target="_blank">results</a>] [<a href="http://build.chromium.org/p/undefined/builders/a%20builder" target="_blank">builder</a>]
            </td>
            <td class="days-old">2015-02-11T23:39:20.033790 (4 days, 00:20:00)</td>
          </tr>
        `);

  // Fast forward past one week.
  Date._now = oldDate.parse('2015-02-19T23:59:20.033790');

  html = builderstate.generateHtml(oneMaster);

  equal(html, `
          <tr>
            <td>a test</td>
            <td>
               a master:a builder
               [<a href="http://test-results.appspot.com/testfile?testtype=a%20test&builder=a%20builder&master=undefined" target="_blank">results</a>] [<a href="http://build.chromium.org/p/undefined/builders/a%20builder" target="_blank">builder</a>]
            </td>
            <td class="weeks-old">2015-02-11T23:39:20.033790 (8 days, 00:20:00)</td>
          </tr>
        `);

  // Check null timestamp for builder.
  oneMaster.masters[0].tests['a test'].builders['a builder'] = null;
  html = builderstate.generateHtml(oneMaster);

  equal(html, `
          <tr>
            <td>a test</td>
            <td>
               a master:a builder
               [<a href="http://test-results.appspot.com/testfile?testtype=a%20test&builder=a%20builder&master=undefined" target="_blank">results</a>] [<a href="http://build.chromium.org/p/undefined/builders/a%20builder" target="_blank">builder</a>]
            </td>
            <td class=""> (never)</td>
          </tr>
        `);

  Date = oldDate;
});

