exports.endpoint = async function(request, response) {
  const got = require("got@11.8.2")
  const jsdom = require("jsdom@16.5.1");
  const humanize = require("humanize-plus@1.8.2");

  var resp = await got("https://github.com/EnricoMi/publish-unit-test-result-action/pkgs/container/publish-unit-test-result-action");
  const html = new jsdom.JSDOM(resp.body);

  // total downloads
  const spans = Array.from(html.window.document.getElementsByTagName('span'))
  const downloads = spans.filter(span => span.textContent == 'Total downloads')
                         .map(span => span.nextElementSibling.title)
  const pulls = humanize.compactInteger(downloads[0], 1);

  // downloads over last 30 days
  const rects = Array.from(html.window.document.getElementsByTagName('rect'))
  const counts = rects.map(rect => rect.getAttribute("data-merge-count")).map(c => parseInt(c))
  const sum = counts.reduce((a, b) => a + b, 0)
  const per_day = humanize.compactInteger(sum / 30, 1);

  // json response
  var resp = {
    subject: 'Docker pulls',
    status: `${pulls} (${per_day}/day)`,
    color: "blue"
  }
  response.end(JSON.stringify(resp));
}
