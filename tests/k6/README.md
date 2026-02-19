# Moirai Load Testing with k6

This directory contains load tests for the Moirai service using [k6](https://k6.io/).

## Prerequisites

- [k6](https://k6.io/docs/get-started/installation/) installed on your machine.

## Running the tests

You can run the tests against the deployed environment or a local instance.

### Default (Production/Staging)

```bash
k6 run load_test.js
```

### Custom Environment

Override the base URL or credentials using environment variables:

```bash
k6 run -e BASE_URL=http://localhost:8088 -e ADMIN_USERNAME=admin -e ADMIN_PASSWORD=secret load_test.js
```

## Scenarios

The current script (`load_test.js`) performs a smoke/load test with the following stages:
1. **Ramp Up**: 30s to 20 virtual users.
2. **Sustain**: 1m at 20 virtual users.
3. **Ramp Down**: 30s to 0 virtual users.

It checks:
- `/api/health`
- `/api/feeds`
- `/api/articles`
