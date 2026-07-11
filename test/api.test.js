'use strict';

const request = require('supertest');
const { app } = require('../src/index');

describe('ponteo-project API', () => {
  test('GET /health returns 200', async () => {
    const res = await request(app).get('/health');
    expect(res.statusCode).toBe(200);
    expect(res.body.status).toBe('ok');
  });

  test('GET /ready returns 200', async () => {
    const res = await request(app).get('/ready');
    expect(res.statusCode).toBe(200);
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
