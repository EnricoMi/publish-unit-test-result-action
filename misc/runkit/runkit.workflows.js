const opts = { headers: { Authorization: `bearer ${process.env['github.token']}` }, responseType: 'json' };
var search = query => require("got")(`https://api.github.com/search/code?${query}`, opts);

exports.endpoint = async function(request, response) {
  var query = q => `q=%22${q}%22+path%3A.github%2Fworkflows%2F+language%3AYAML&type=Code`;
  var build_count = search(query('publish-unit-test-result-action'));
  var count = Promise.all([build_count])
                     .then((counts) => counts.map(c => c.body.total_count))
                     .then((counts) => counts.reduce((a, b) => a + b, 0));

  var resp = {
    subject: 'GitHub Workflows',
    status: await count,
    color: "blue"
  }

  response.end(JSON.stringify(resp));
}