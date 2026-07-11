'use strict';

const { getBuildInfo } = require('../src/version');

describe('getBuildInfo', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  test('returns package defaults when env vars unset', () => {
    delete process.env.VERSION;
    delete process.env.VCS_REF;
    delete process.env.BUILD_DATE;

    const info = getBuildInfo();
    expect(info.service).toBe('ponteo-project');
    expect(info.version).toBe('1.0.0');
    expect(info.gitSha).toBe('dev');
    expect(info.buildDate).toBeNull();
  });

  test('prefers build-time env vars', () => {
    process.env.VERSION = 'pr-13-abc123';
    process.env.VCS_REF = 'abc123def456';
    process.env.BUILD_DATE = '2026-07-11T00:00:00Z';

    const info = getBuildInfo();
    expect(info.version).toBe('pr-13-abc123');
    expect(info.gitSha).toBe('abc123def456');
    expect(info.buildDate).toBe('2026-07-11T00:00:00Z');
  });
});
