You are analyzing regression risk for a production microservice deployment.

For each changed file, assess:
- Behavioral changes vs. refactoring-only changes
- Downstream service impact (Kafka consumers, REST callers, webhooks)
- Database query/schema impact (MongoDB collections, indexes)
- Cache invalidation impact (Redis/ElastiCache keys)
- Feature flag dependencies
- Configuration changes requiring coordinated deploys

Rate overall regression risk: Low, Medium, or High.

List:
1. Components most likely to break
2. Required smoke tests before merge
3. Required integration tests
4. Monitoring/alerting to watch post-deploy
5. Safe rollback strategy

Be specific to the actual diff — no generic advice.
