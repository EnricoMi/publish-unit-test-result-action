const opts = { headers: { Authorization: `bearer ${process.env['github.token']}`, Accept: "application/vnd.github.v3+json" } };

exports.endpoint = async function(request, response) {
  var resp = await require("got")("http://github.com-enricomi.s3-website.eu-central-1.amazonaws.com/publish-unit-test-result.pull.count", opts);
  var counts = resp.body

  const humanize = require("humanize-plus")
  const pulls = humanize.compactInteger(counts, 1)

  var resp = {
    subject: 'Docker pulls',
    status: `${pulls}/month`,
    color: "blue"
  }

  response.end(JSON.stringify(resp));
}
