# Security Enhancement Plan for Moirai

## Overview
This document outlines planned security improvements for the Moirai press review platform. The application currently uses HTTP Basic Authentication and has some security gaps that need addressing.

---

## 1. Authentication & Authorization

### 1.1 Replace HTTP Basic Auth with Session-Based or Token-Based Authentication
**Priority: HIGH**

**Current State:**
- Uses HTTP Basic Auth with credentials sent in every request
- Single username/password for all users
- No session management
- Credentials stored as plain environment variables

**Proposed Enhancement:**
- Implement JWT (JSON Web Token) or session-based authentication
- Add login endpoint that issues tokens/creates sessions
- Store session data securely (Redis or encrypted cookies)
- Implement token refresh mechanism
- Add logout functionality

**Benefits:**
- Better security - credentials not sent with every request
- Support for token expiration
- Ability to revoke sessions
- Foundation for multi-user support

---

### 1.2 Multi-User Support with Role-Based Access Control (RBAC)
**Priority: MEDIUM**

**Current State:**
- Single shared credentials for all users
- No user management
- No role differentiation

**Proposed Enhancement:**
- Add user management system (users table in CouchDB)
- Implement roles: `admin`, `editor`, `viewer`
- Define permissions per role:
  - **Admin**: Full access (create/edit/delete all resources, manage users, change config)
  - **Editor**: Create/edit/delete feeds, articles, events, trends (no user/config management)
  - **Viewer**: Read-only access
- Add endpoints for user CRUD operations (admin only)
- Store password hashes (bcrypt or argon2) instead of plaintext

**Benefits:**
- Multi-tenant capability
- Principle of least privilege
- Audit trail of who did what
- Better collaboration support

---

### 1.3 Userspace Access Control
**Priority: MEDIUM**

**Current State:**
- Userspaces exist but no access control
- Any authenticated user can access any userspace
- Userspace filtering is client-side only

**Proposed Enhancement:**
- Implement userspace ownership model
- Users assigned to one or more userspaces
- Admins can access all userspaces
- Editors/Viewers restricted to assigned userspaces
- Server-side userspace filtering on all queries
- Userspace access validation on all write operations

**Benefits:**
- Data isolation between teams/projects
- Multi-tenant security
- Prevent unauthorized cross-userspace access

---

## 2. API Security

### 2.1 Rate Limiting
**Priority: HIGH**

**Current State:**
- No rate limiting
- Vulnerable to brute force attacks
- Vulnerable to DoS attacks

**Proposed Enhancement:**
- Implement rate limiting middleware using `flask-limiter`
- Different limits for different endpoint types:
  - Login: 5 attempts per 15 minutes per IP
  - Read operations: 100 requests per minute per user
  - Write operations: 20 requests per minute per user
  - Feed refresh: 5 requests per minute per user
- Return `429 Too Many Requests` with `Retry-After` header
- Store rate limit data in Redis for distributed deployments

**Benefits:**
- Protection against brute force attacks
- DoS/DDoS mitigation
- Resource consumption control

---

### 2.2 Input Validation & Sanitization
**Priority: HIGH**

**Current State:**
- Limited input validation
- No sanitization for HTML/XSS
- Trust user-provided URLs without validation

**Proposed Enhancement:**
- Use Pydantic or marshmallow for request validation
- Validate all user inputs:
  - Feed URLs: validate URL format, check allowed schemes (http/https only)
  - Event/Trend titles: max length, no script tags
  - Namespace GUIDs: validate UUID format
- Sanitize HTML content from RSS feeds before storage
- Implement Content Security Policy (CSP) headers
- Add URL allowlist/blocklist for feed sources

**Benefits:**
- Prevent XSS attacks
- Prevent SSRF attacks
- Data integrity
- Better error messages

---

### 2.3 CORS Configuration
**Priority: MEDIUM**

**Current State:**
- CORS headers not properly configured
- OPTIONS requests allowed without auth
- No origin validation

**Proposed Enhancement:**
- Configure Flask-CORS properly
- Define allowed origins explicitly (not `*`)
- Restrict allowed methods per endpoint
- Implement CORS preflight caching
- Add origin validation in environment config

**Benefits:**
- Prevent unauthorized cross-origin requests
- Better browser security
- Explicit origin control

---

### 2.4 Re-enable CSRF Protection
**Priority: MEDIUM**

**Current State:**
- CSRF protection disabled (`WTF_CSRF_ENABLED = False`)
- Vulnerable to CSRF attacks

**Proposed Enhancement:**
- Enable CSRF protection for all state-changing operations
- Implement CSRF token generation and validation
- Exclude read-only GET endpoints from CSRF checks
- Add CSRF token to session or JWT claims
- Update frontend to include CSRF tokens in requests

**Benefits:**
- Prevent Cross-Site Request Forgery attacks
- Ensure requests originate from legitimate application

---

## 3. Data Security

### 3.1 Secrets Management
**Priority: HIGH**

**Current State:**
- Secrets in environment variables
- Default passwords in docker-compose (`password`, `secret`)
- CouchDB credentials in connection string
- No secrets rotation

**Proposed Enhancement:**
- Use Docker secrets or Kubernetes secrets
- Implement secrets rotation schedule
- Use strong random passwords generated at deployment
- Store secrets in HashiCorp Vault or AWS Secrets Manager (production)
- Remove default password fallbacks
- Add startup validation to ensure secrets are set

**Benefits:**
- Prevent credential exposure
- Centralized secrets management
- Compliance with security standards
- Audit trail for secrets access

---

### 3.2 Database Security
**Priority: HIGH**

**Current State:**
- CouchDB exposed on port 5984
- Admin credentials in environment
- No connection encryption
- No per-user database access control

**Proposed Enhancement:**
- Remove CouchDB port exposure (internal only)
- Use CouchDB per-user permissions
- Enable SSL/TLS for CouchDB connections
- Implement connection pooling with authentication
- Add database backup encryption
- Regular security updates for CouchDB

**Benefits:**
- Prevent unauthorized database access
- Data in transit encryption
- Defense in depth

---

### 3.3 Password Storage
**Priority: HIGH** (when multi-user implemented)

**Current State:**
- Single shared password in env variable
- No password policy

**Proposed Enhancement:**
- Hash passwords with bcrypt or argon2
- Implement password complexity requirements:
  - Minimum 12 characters
  - Mix of uppercase, lowercase, numbers, symbols
- Password change functionality
- Password expiration policy (90 days)
- Prevent password reuse (last 5 passwords)

**Benefits:**
- Secure credential storage
- Compliance with security standards
- Reduced risk from password breaches

---

## 4. Network Security

### 4.1 HTTPS/TLS Enforcement
**Priority: HIGH**

**Current State:**
- HTTP only (port 8088)
- No TLS encryption
- Credentials sent over plain HTTP

**Proposed Enhancement:**
- Add HTTPS support with TLS certificates
- Redirect HTTP to HTTPS
- Use Let's Encrypt for certificates (or cert-manager in K8s)
- Implement HSTS (HTTP Strict Transport Security) headers
- Configure strong TLS ciphers (TLS 1.2+)
- Add TLS termination at reverse proxy (nginx/traefik)

**Benefits:**
- Encrypted data in transit
- Prevent man-in-the-middle attacks
- Browser security warnings prevention
- Required for production deployment

---

### 4.2 Reverse Proxy & Security Headers
**Priority: MEDIUM**

**Current State:**
- Flask app directly exposed
- No security headers
- No request filtering

**Proposed Enhancement:**
- Deploy behind nginx or traefik reverse proxy
- Add security headers:
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `Content-Security-Policy` (CSP)
  - `Referrer-Policy: no-referrer-when-downgrade`
- Implement request size limits
- Add request filtering for common attacks

**Benefits:**
- Defense against clickjacking
- XSS protection
- MIME type sniffing prevention
- Additional security layer

---

## 5. MCP Server Security

### 5.1 MCP Userspace Isolation
**Priority: HIGH**

**Current State:**
- Userspace required for tools but not enforced at transport level
- HTTP SSE endpoint exposed on port 8090
- No authentication on MCP server

**Proposed Enhancement:**
- Add authentication to MCP server (shared secret or JWT)
- Enforce userspace validation on all tool calls
- Implement userspace quota limits (max feeds, events, trends per userspace)
- Add audit logging for all MCP tool invocations
- Rate limit MCP tool calls per userspace

**Benefits:**
- Prevent unauthorized MCP access
- Userspace data isolation
- Resource consumption control
- Audit trail for agent actions

---

### 5.2 MCP Request Validation
**Priority: MEDIUM**

**Current State:**
- Tool parameters validated minimally
- URLs accepted without verification
- No size limits on tool inputs

**Proposed Enhancement:**
- Strict parameter validation for all tools
- URL validation before fetching feeds (prevent SSRF)
- Size limits on tool inputs (max title length, etc.)
- Reject malformed GUIDs
- Sanitize all text inputs

**Benefits:**
- Prevent SSRF attacks
- Data integrity
- Resource consumption control

---

## 6. Logging & Monitoring

### 6.1 Security Audit Logging
**Priority: MEDIUM**

**Current State:**
- Basic Flask request logging only
- No security event logging
- No audit trail

**Proposed Enhancement:**
- Log all authentication attempts (success/failure)
- Log all authorization failures
- Log all configuration changes
- Log all MCP tool invocations
- Include: timestamp, user, IP, action, resource, result
- Send logs to centralized logging (ELK stack, Splunk, etc.)
- Implement log retention policy

**Benefits:**
- Security incident investigation
- Compliance requirements
- Anomaly detection
- Forensic analysis

---

### 6.2 Security Monitoring & Alerts
**Priority: MEDIUM**

**Current State:**
- No monitoring
- No alerting

**Proposed Enhancement:**
- Monitor failed login attempts (alert on 10+ failures)
- Monitor rate limit hits
- Monitor unusual activity patterns
- Monitor error rates
- Implement health check endpoints
- Set up alerting (email, Slack, PagerDuty)
- Add metrics collection (Prometheus)

**Benefits:**
- Early threat detection
- Incident response capability
- System health visibility

---

## 7. Dependency & Container Security

### 7.1 Dependency Scanning
**Priority: MEDIUM**

**Current State:**
- Dependabot enabled
- No vulnerability scanning in CI/CD

**Proposed Enhancement:**
- Add Snyk or Trivy to CI/CD pipeline
- Scan Python dependencies (requirements.txt)
- Scan JavaScript dependencies (package.json)
- Block builds with high/critical vulnerabilities
- Regular dependency updates schedule
- Use `pip-audit` for Python dependencies

**Benefits:**
- Identify known vulnerabilities
- Automated security updates
- Reduce attack surface

---

### 7.2 Container Image Security
**Priority: MEDIUM**

**Current State:**
- Using `python:3-slim` base image
- Running as root user
- No image scanning

**Proposed Enhancement:**
- Use minimal base image (distroless or alpine)
- Run as non-root user (already has appuser)
- Scan images with Trivy/Clair in CI/CD
- Use multi-stage builds (already done)
- Pin base image versions with SHA256
- Regular base image updates
- Remove unnecessary packages

**Benefits:**
- Reduced attack surface
- Faster vulnerability detection
- Container escape prevention

---

## 8. Frontend Security

### 8.1 Vue.js Security Best Practices
**Priority: MEDIUM**

**Current State:**
- Basic Vue.js app
- No CSP implementation
- No XSS prevention beyond Vue's defaults

**Proposed Enhancement:**
- Implement Content Security Policy
- Use `v-text` instead of `v-html` where possible
- Sanitize any user-generated HTML (DOMPurify)
- Enable SRI (Subresource Integrity) for CDN resources
- Implement security headers for static files
- Regular Vue.js security updates

**Benefits:**
- XSS prevention
- Supply chain attack prevention
- Client-side security hardening

---

### 8.2 Sensitive Data Handling
**Priority: HIGH**

**Current State:**
- No client-side encryption
- LocalStorage used for chat history (potentially sensitive)

**Proposed Enhancement:**
- Don't store sensitive data in localStorage/sessionStorage
- Clear sensitive data on logout
- Implement auto-logout after inactivity (30 minutes)
- Use HttpOnly cookies for auth tokens
- Encrypt sensitive data before storing (if necessary)

**Benefits:**
- Reduce XSS impact
- Prevent token theft
- Better session security

---

## 9. Compliance & Governance

### 9.1 Security Documentation
**Priority: LOW**

**Current State:**
- README with basic setup
- No security documentation

**Proposed Enhancement:**
- Create SECURITY.md with:
  - Security reporting process
  - Supported versions
  - Security update policy
- Create security architecture diagram
- Document authentication flow
- Document authorization model
- Create incident response plan

**Benefits:**
- Clear security processes
- Responsible disclosure
- Team alignment

---

### 9.2 Security Testing
**Priority: MEDIUM**

**Current State:**
- Playwright tests for functionality
- Basic security tests added

**Proposed Enhancement:**
- Expand security test suite:
  - Authentication bypass tests
  - Authorization tests
  - CSRF tests
  - XSS tests
  - SQL injection tests (if applicable)
- Add OWASP ZAP scanning to CI/CD
- Perform regular penetration testing
- Implement security code review process

**Benefits:**
- Early vulnerability detection
- Regression prevention
- Security validation

---

## Implementation Priority

### Phase 1 (Critical - Immediate)
1. HTTPS/TLS enforcement
2. Secrets management
3. Rate limiting
4. Input validation
5. Database security hardening

### Phase 2 (High - 1-2 months)
1. JWT/Session authentication
2. MCP authentication
3. Dependency scanning
4. Security audit logging
5. Frontend sensitive data handling

### Phase 3 (Medium - 3-6 months)
1. Multi-user & RBAC
2. Namespace access control
3. CSRF protection
4. Security monitoring
5. Container security scanning

### Phase 4 (Lower Priority - 6+ months)
1. CORS fine-tuning
2. Security documentation
3. Comprehensive security testing
4. Advanced monitoring & alerting

---

## Notes

- This plan assumes production deployment is the goal
- Some enhancements may not be needed for single-user local development
- Implementation should follow security testing to validate effectiveness
- Regular security audits recommended after implementation
- Consider hiring security consultant for penetration testing before production launch
