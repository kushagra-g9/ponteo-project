'use strict';

const express = require('express');
const { sum } = require('./sum');

const app = express();
const PORT = Number(process.env.PORT) || 3000;

app.get('/health', (req, res) => res.status(200).json({ status: 'ok' }));
app.get('/ready', (req, res) => res.status(200).json({ status: 'ready' }));

app.get('/sum', (req, res) => {
  const a = Number(req.query.a);
  const b = Number(req.query.b);
  if (Number.isNaN(a) || Number.isNaN(b)) {
    return res.status(400).json({ error: 'query params a and b must be numbers' });
  }
  return res.status(200).json({ result: sum(a, b) });
});

if (require.main === module) {
  app.listen(PORT, () => {
    // eslint-disable-next-line no-console
    console.log(JSON.stringify({ level: 'info', msg: 'ponteo-project started', port: PORT }));
  });
}

module.exports = { app };
