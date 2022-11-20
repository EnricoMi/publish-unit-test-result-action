exports.endpoint = async function(request, response) {
  resp = await require("got@11.8.2")("http://github.com-enricomi.s3-website.eu-central-1.amazonaws.com/publish-unit-test-result.workflows");
  var workflows = parseInt(resp.body);

  var resp = {
    subject: 'GitHub Workflows',
    status: workflows.toLocaleString('en-US'),
    color: 'blue'
  }

  response.end(JSON.stringify(resp));
}
