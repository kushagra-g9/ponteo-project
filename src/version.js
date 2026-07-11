'use strict';

const pkg = require('../package.json');

/**
 * Build metadata injected at image build time (see Dockerfile ARG/ENV).
 * Falls back to package.json / "unknown" for local dev and tests.
 */
function getBuildInfo() {
  return {
    service: pkg.name,
    version: process.env.VERSION || pkg.version,
    gitSha: process.env.VCS_REF || 'dev',
    buildDate: process.env.BUILD_DATE || null,
  };
}

module.exports = { getBuildInfo };
