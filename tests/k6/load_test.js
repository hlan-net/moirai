import http from 'k6/http';
import { check, sleep } from 'k6';
import { b64encode } from 'k6/encoding';

// Configuration
export const options = {
  stages: [
    { duration: '30s', target: 20 }, // Ramp up to 20 users
    { duration: '1m', target: 20 },  // Stay at 20 users
    { duration: '30s', target: 0 },  // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests must complete below 500ms
    http_req_failed: ['rate<0.01'],   // http errors should be less than 1%
  },
};

// Authentication credentials (can be overridden via environment variables)
const USERNAME = __ENV.ADMIN_USERNAME || 'admin';
const PASSWORD = __ENV.ADMIN_PASSWORD || 'changeme';
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8088';

export default function () {
  const credentials = `${USERNAME}:${PASSWORD}`;
  const encodedCredentials = b64encode(credentials);
  const params = {
    headers: {
      'Authorization': `Basic ${encodedCredentials}`,
    },
  };

  // 1. Health Check
  const resHealth = http.get(`${BASE_URL}/api/health`);
  check(resHealth, {
    'health status is 200': (r) => r.status === 200,
  });

  // 2. List Feeds
  const resFeeds = http.get(`${BASE_URL}/api/feeds`, params);
  check(resFeeds, {
    'feeds status is 200': (r) => r.status === 200,
    'feeds returned array': (r) => {
        try {
            return Array.isArray(r.json());
        } catch(e) {
            return false;
        }
    },
  });

  // 3. List Articles
  const resArticles = http.get(`${BASE_URL}/api/articles?limit=10`, params);
  check(resArticles, {
    'articles status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
