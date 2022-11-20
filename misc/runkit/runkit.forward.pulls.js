exports.endpoint = async function(request, response) {
  var total = await require("got@11.8.2")("http://github.com-enricomi.s3-website.eu-central-1.amazonaws.com/publish-unit-test-result.pull.total").body;
  var month = await require("got@11.8.2")("http://github.com-enricomi.s3-website.eu-central-1.amazonaws.com/publish-unit-test-result.pull.month").body;

  const humanize = require("humanize-plus@1.8.2")
  const all = humanize.compactInteger(total, 1)
  const day = humanize.compactInteger(month/30, 1)

  var resp = {
    subject: 'Docker pulls',
    status: `${all} (${day}/day)`,
    color: 'blue'
  }

  response.end(JSON.stringify(resp));
}
