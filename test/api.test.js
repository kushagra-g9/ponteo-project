'use strict';

const request = require('supertest');
const { app } = require('../src/index');

describe('ponteo-project API', () => {
  test('GET /health returns 200 with uptime metadata', async () => {
    const res = await request(app).get('/health');
    expect(res.statusCode).toBe(200);
    expect(res.body.status).toBe('ok');
    expect(typeof res.body.uptimeSeconds).toBe('number');
    expect(res.body.uptimeSeconds).toBeGreaterThanOrEqual(0);
    expect(res.body.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  test('GET /ready returns 200', async () => {
    const res = await request(app).get('/ready');
    expect(res.statusCode).toBe(200);
    expect(res.body.status).toBe('ready');
    expect(res.body.version).toBeDefined();
    expect(res.body.gitSha).toBeDefined();
  });

  test('GET /version returns build metadata', async () => {
    const res = await request(app).get('/version');
    expect(res.statusCode).toBe(200);
    expect(res.body.service).toBe('ponteo-project');
    expect(res.body.version).toBeDefined();
    expect(res.body.gitSha).toBeDefined();
  });

  test('GET /sum returns computed result', async () => {
    const res = await request(app).get('/sum?a=2&b=5');
    expect(res.statusCode).toBe(200);
    expect(res.body.result).toBe(7);
  });

  test('GET /sum validates input', async () => {
    const res = await request(app).get('/sum?a=foo&b=5');
    expect(res.statusCode).toBe(400);
  });
});
