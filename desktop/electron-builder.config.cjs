const packageJson = require("./package.json");

const config = { ...packageJson.build };
const repository = (process.env.MLIB_GITHUB_REPOSITORY || "").trim();
const repositoryMatch = /^([^/\s]+)\/([^/\s]+)$/.exec(repository);

if (repositoryMatch) {
  config.publish = [{
    provider: "github",
    owner: repositoryMatch[1],
    repo: repositoryMatch[2],
    releaseType: "release",
  }];
}

module.exports = config;
