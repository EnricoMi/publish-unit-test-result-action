exports.endpoint = async function(request, response) {
  var got = require("got");
  url = 'https://api.github.com/search/code?q=%22publish-unit-test-result-action%22+path%3A.github%2Fworkflows%2F+language%3AYAML&type=Code'

  var count = (await got(url, { headers: { Authorization: `bearer ${process.env['github.token']}` }, responseType: 'json' })).body.total_count;
 
  var resp = {
    subject: 'GitHub Workflows',
    status: count,
    color: "blue"
  }

  response.end(JSON.stringify(resp));
}
