async function get_count(url) {
    var response = await require("got")(url);
    const jsdom = require("jsdom");
    const html = new jsdom.JSDOM(response.body);
    const spans = Array.from(html.window.document.getElementsByTagName('span'))
    return spans.filter(span => span.textContent == 'Last 30 days')
                .map(span => span.nextElementSibling.textContent)
                .map(count => Number(count.replace(",", "")))[0];
}

const opts = { headers: { Authorization: `bearer ${process.env['github.token']}`, Accept: "application/vnd.github.v3+json" }, responseType: 'json' };

exports.endpoint = async function(request, response) {
  var resp = await require("got")("https://api.github.com/users/EnricoMi/packages/container/publish-unit-test-result-action/versions", opts);
  var counts = resp.body
                 .filter(version => version.metadata.package_type == "container")
                 .filter(version => version.metadata.container.tags.filter(tag => tag.startsWith("v") && tag.includes(".") && ["v1.7","v1.8","v1.9","v1.13","v1.14"].indexOf(tag) == -1).length > 0)
                 .slice(0, 10)
                 .map(version => version.html_url)
                 .map(url => get_count(url));
  counts = await Promise.all(counts)
  const count = counts.reduce((a,b) => a + b, 0)

  const humanize = require("humanize-plus")
  const pulls = humanize.compactInteger(count, 1)

  var resp = {
    subject: 'Docker pulls',
    status: `${pulls}/month`,
    color: "blue"
  }

  response.end(JSON.stringify(resp));
}
