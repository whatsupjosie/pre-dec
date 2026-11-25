# Phase 4: Deployment — PubCast Live

**Timeline:** Days 8-14 | **Days to Launch:** 7 remaining  
**Goal:** Ship to production safely  
**Focus:** CI/CD, staging, monitoring, rollback

---

## DEPLOYMENT CHECKLIST

### Pre-Deployment (Day 8)

- [ ] All Phase 3 tests pass (responsive, accessible, errors clean)
- [ ] Code review complete (no TODOs, clean comments)
- [ ] Assets optimized (GLB files compressed)
- [ ] Documentation updated
- [ ] Security audit done (no XSS, CORS, input validation)
- [ ] Performance baseline established (55-60 FPS)

### Staging Deployment (Days 9-10)

- [ ] Deploy to staging server
- [ ] Run full test suite on staging
- [ ] Load test (100+ concurrent users)
- [ ] Security scan (no vulnerabilities)
- [ ] Verify all features work end-to-end
- [ ] Collect metrics (latency, errors, FPS)

### Production Deployment (Days 11-12)

- [ ] Final code review
- [ ] Blue-green deployment setup
- [ ] Deploy to production
- [ ] Smoke tests pass (basic functionality)
- [ ] Monitor for 1 hour (errors, latency)
- [ ] Gradual traffic increase (25% → 50% → 100%)

### Post-Deployment (Days 13-14)

- [ ] 24-hour monitoring
- [ ] Performance metrics within targets
- [ ] Error rate < 0.1%
- [ ] User feedback positive
- [ ] Documentation complete
- [ ] Team trained on system

---

## CI/CD PIPELINE (GitHub Actions Example)

Create file: `.github/workflows/pubcast-deploy.yml`

```yaml
name: PubCast CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '16'
      
      - name: Install dependencies
        run: npm install
      
      - name: Run linter
        run: npm run lint
      
      - name: Run unit tests
        run: npm test
      
      - name: Build assets
        run: npm run build
      
      - name: Run integration tests
        run: npm run test:integration

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run security audit
        run: npm audit --audit-level=moderate
      
      - name: Check dependencies
        run: npm outdated

  deploy-staging:
    needs: [test, security]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v2
      
      - name: Deploy to staging
        env:
          STAGING_SERVER: ${{ secrets.STAGING_SERVER }}
          STAGING_KEY: ${{ secrets.STAGING_KEY }}
        run: |
          echo "Deploying to staging..."
          ssh -i $STAGING_KEY ubuntu@$STAGING_SERVER \
            "cd /var/www/pubcast-staging && git pull origin main && npm install"

  deploy-production:
    needs: [test, security]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production
    steps:
      - uses: actions/checkout@v2
      
      - name: Blue-Green Deploy
        env:
          PROD_SERVER: ${{ secrets.PROD_SERVER }}
          PROD_KEY: ${{ secrets.PROD_KEY }}
        run: |
          echo "Starting blue-green deployment..."
          ssh -i $PROD_KEY ubuntu@$PROD_SERVER "bash /opt/deploy-pubcast.sh"
```

---

## DEPLOYMENT SCRIPT (Bash)

Create file: `/opt/deploy-pubcast.sh`

```bash
#!/bin/bash
set -e

echo "═══════════════════════════════════════════════════════════════"
echo "PubCast Deployment Script"
echo "═══════════════════════════════════════════════════════════════"

REPO="/var/www/pubcast"
BLUE="/var/www/pubcast-blue"
GREEN="/var/www/pubcast-green"
CURRENT="/var/www/pubcast"

# Determine which is active
if [ -L "$CURRENT" ]; then
  ACTIVE=$(readlink "$CURRENT")
  if [ "$ACTIVE" == "$BLUE" ]; then
    NEXT=$GREEN
    PREV=$BLUE
  else
    NEXT=$BLUE
    PREV=$GREEN
  fi
else
  NEXT=$BLUE
  PREV=$GREEN
fi

echo "Active: $ACTIVE"
echo "Deploying to: $NEXT"

# 1. Prepare new version
mkdir -p "$NEXT"
cd "$REPO"
git fetch origin main
git checkout origin/main

# 2. Copy code to next version
cp -r control.html avatar_*.js /var/www/assets "$NEXT/"

# 3. Build assets (if needed)
npm install
npm run build

# 4. Run tests on new version
cd "$NEXT"
npm test || exit 1

# 5. Health check on new version
echo "Waiting for new version to be ready..."
sleep 5

curl -f http://localhost:3001/health || exit 1

# 6. Switch traffic
echo "Switching traffic to new version..."
rm "$CURRENT"
ln -s "$NEXT" "$CURRENT"

# 7. Verify switch
if curl -f http://localhost:3000/health > /dev/null; then
  echo "✓ Deployment successful"
  
  # Optional: Keep previous for rollback
  echo "Previous version available at: $PREV"
  
else
  echo "✗ Health check failed, rolling back..."
  rm "$CURRENT"
  ln -s "$PREV" "$CURRENT"
  exit 1
fi

echo "═══════════════════════════════════════════════════════════════"
echo "Deployment complete!"
echo "═══════════════════════════════════════════════════════════════"
```

---

## MONITORING SETUP (Datadog/New Relic)

### Key Metrics to Track

```javascript
// Add to control.html
const metrics = {
  pageLoadTime: performance.now(),
  avatarLoadTime: null,
  firstFrameTime: null,
  fps: 0,
  errors: 0,
  wsConnectTime: null,
};

// Report to monitoring service
function reportMetrics() {
  const payload = {
    timestamp: new Date().toISOString(),
    pageLoadTime: metrics.pageLoadTime,
    avatarLoadTime: metrics.avatarLoadTime,
    fps: metrics.fps,
    errors: metrics.errors,
    wsConnected: window.AvatarMotionRuntime?.isConnected,
  };
  
  // Send to your monitoring endpoint
  fetch('/api/metrics', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(err => console.error('Metrics report failed:', err));
}

// Report every 30 seconds
setInterval(reportMetrics, 30000);
```

### Alerts to Configure

**Critical (page down):**
- Error rate > 1%
- Page load time > 5 seconds
- WebSocket connection loss > 30 seconds

**Warning (needs attention):**
- Error rate > 0.1%
- Page load time > 3 seconds
- FPS < 30
- Memory > 200 MB

**Info (for trending):**
- Average load time
- Average FPS
- Concurrent users
- Geographic distribution

---

## LOAD TESTING (Days 9-10)

Use Apache Bench or Locust:

```bash
# Simple load test: 100 requests, 10 concurrent
ab -n 100 -c 10 https://staging.pubcast.app/control.html

# Or with Locust (Python):
# Create locustfile.py
from locust import HttpUser, task, between

class PubCastUser(HttpUser):
  wait_time = between(1, 3)
  
  @task(3)
  def load_main(self):
    self.client.get('/control.html')
  
  @task(1)
  def simulate_motion(self):
    self.client.post('/api/avatar-motion', json={
      'avatar_id': 'manny',
      'bones': [{'name': 'head', 'quaternion': [0, 0, 0.1, 0.99]}],
      'duration': 500
    })

# Run: locust -f locustfile.py --host=https://staging.pubcast.app
```

Expected results:
- ✅ 99th percentile response time < 1 second
- ✅ Error rate < 0.1%
- ✅ No memory leaks
- ✅ CPU < 80%

---

## ROLLBACK PROCEDURE

### Quick Rollback (< 1 minute)

```bash
# If using blue-green deployment
# Just switch symlink back to previous version

ln -sfn /var/www/pubcast-blue /var/www/pubcast
# or
ln -sfn /var/www/pubcast-green /var/www/pubcast

# Verify
curl https://pubcast.app/control.html
```

### Full Rollback (if needed)

```bash
# 1. Check git log for previous commit
git log --oneline | head -5

# 2. Revert to previous version
git revert <commit-hash>
git push origin main

# 3. Re-run deployment (will automatically deploy reverted version)
bash /opt/deploy-pubcast.sh
```

### Datadog Rollback Alert
```
alert when error_rate > 1% for 5 minutes {
  notify on-call
  message: "PubCast error rate critical, consider rollback"
  action: automatic rollback (requires approval)
}
```

---

## STAGING SMOKE TESTS

Create file: `tests/smoke-test.js`

```javascript
const http = require('http');

function test(name, fn) {
  try {
    fn();
    console.log(`✓ ${name}`);
  } catch (err) {
    console.error(`✗ ${name}: ${err.message}`);
    process.exit(1);
  }
}

test('Server is up', () => {
  // curl https://staging.pubcast.app/control.html
  // expect: 200 OK
});

test('Assets load', () => {
  // GET /control.html
  // GET /avatar_glb_motion_consumer.js
  // GET /avatar_motion_runtime.js
  // All should return 200
});

test('API endpoints respond', () => {
  // GET /health → 200
  // GET /api/config → 200
  // POST /api/avatar-motion → 200
});

test('WebSocket connects', () => {
  // Connect to ws://staging.pubcast.app/ws/motion
  // Send ping
  // Receive pong
});

test('Database accessible', () => {
  // SELECT 1 from users
  // Should succeed
});

console.log('✓ All smoke tests passed');
```

Run before production deployment:
```bash
npm test -- tests/smoke-test.js
```

---

## PRODUCTION CHECKLIST

### Day 11: Deployment

- [ ] Code freeze (no new changes)
- [ ] All tests passing (unit, integration, smoke)
- [ ] Documentation updated
- [ ] Team notified of deployment window
- [ ] Rollback procedure tested
- [ ] Monitoring dashboards created
- [ ] On-call team briefed
- [ ] Backup database created
- [ ] SSL/TLS certificates valid
- [ ] DNS settings verified

### Deployment Steps

```
1. [ ] Blue-green prepare (5 min)
2. [ ] Deploy to next version (5 min)
3. [ ] Health check (1 min)
4. [ ] Switch traffic (1 min)
5. [ ] Monitor for 5 minutes (5 min)
6. [ ] Gradual traffic increase 25% (5 min) → check errors
7. [ ] Gradual traffic increase 50% (5 min) → check errors
8. [ ] Full traffic 100% (1 min)
9. [ ] Monitor for 1 hour (60 min)
10. [ ] Declare success ✓
```

**Total: ~1.5 hours for full deployment**

### Post-Deployment Day 12-14

- [ ] Monitor error logs continuously
- [ ] Check performance metrics (FPS, latency)
- [ ] Verify user reports (no complaints)
- [ ] Document any issues
- [ ] Update runbooks
- [ ] Schedule post-mortem if any issues
- [ ] Notify team of success
- [ ] Archive deployment artifacts
- [ ] Plan next release

---

## MONITORING DASHBOARD

Example Prometheus queries:

```
# Error rate (should be < 0.1%)
rate(errors_total[5m]) / rate(requests_total[5m])

# P99 latency (should be < 1s)
histogram_quantile(0.99, http_request_duration_seconds)

# FPS (should be 55-60)
avatar_fps_gauge

# Memory usage (should be < 200MB)
process_resident_memory_bytes / 1024 / 1024

# WebSocket connections (should be stable)
websocket_connections_active
```

---

## LAUNCH DAY (Days 11-12)

### Morning (Pre-Flight)

- [ ] Final health check on staging
- [ ] Team standup (10 min)
- [ ] Deployment plan reviewed
- [ ] Rollback procedure tested
- [ ] Monitoring systems online
- [ ] On-call engineer ready

### Deployment (10:00 AM)

- [ ] Begin blue-green deployment
- [ ] Switch traffic
- [ ] Monitor error rate for 5 min
- [ ] Gradual traffic ramp (25% → 50% → 100%)
- [ ] Monitor for 1 hour
- [ ] Declare launch successful

### Afternoon (Post-Launch)

- [ ] Monitor metrics closely
- [ ] Check user feedback
- [ ] Document any issues
- [ ] Celebrate! 🎉

### Evening (Post-Launch + 12h)

- [ ] Final check on metrics
- [ ] Hand off to support team
- [ ] Schedule post-mortem (if issues)
- [ ] Archive deployment logs

---

## SUCCESS CRITERIA

### Go/No-Go Decision

**GO if:**
- ✅ 7/7 tests passing
- ✅ No critical security issues
- ✅ Performance baseline met
- ✅ Load test successful
- ✅ Monitoring configured
- ✅ Team trained & ready
- ✅ Rollback procedure tested

**NO-GO if:**
- ❌ Any test failing
- ❌ Critical security vulnerability
- ✅ Performance below baseline
- ❌ Load test issues
- ❌ Monitoring incomplete

### Post-Launch Metrics

**Target within 24 hours:**

| Metric | Target | Alert |
|--------|--------|-------|
| Error Rate | < 0.1% | > 0.5% |
| P99 Latency | < 1s | > 2s |
| FPS | 55-60 | < 30 |
| Memory | < 200 MB | > 300 MB |
| Uptime | 99.9% | < 99% |

---

## TIMELINE SUMMARY

```
Day 8:   Pre-deployment checks       ✓ All systems ready
Day 9:   Staging deployment          ✓ Tests pass
Day 10:  Load testing & monitoring   ✓ Metrics baseline
Day 11:  Production deployment       ✓ Blue-green live
Day 12:  24-hour monitoring          ✓ Success metrics met
Day 13:  Support handoff             ✓ Team trained
Day 14:  Documentation complete      ✓ LAUNCH COMPLETE

Days to launch: 7 (Days 8-14)
```

---

## SIGN-OFF

When all deployment checklist items are checked:

✅ Code passes all tests  
✅ Security audit clean  
✅ Staging deployment successful  
✅ Load tests passed  
✅ Production deployment complete  
✅ 24-hour monitoring successful  
✅ Team trained & ready  

**PUBCAST IS LIVE 🚀**

---

**Phase Status:** Ready to deploy  
**Expected Duration:** 7 days  
**Days Remaining:** 7 to launch
