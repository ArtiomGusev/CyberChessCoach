Purpose

Testing ensures system reliability and architectural discipline.

A push is allowed only when all tests pass.

Core Rule

Never push code before all tests pass.

This rule is absolute.

Testing Principles

Tests must be:

objective

reproducible

deterministic

meaningful

Tests must not be weakened to force success.

Test Categories
Unit Tests

Test individual components.

Examples:

mistake classifier

evaluation parser

analytics calculator

context builder

Integration Tests

Test component interactions.

Examples:

API → engine
API → coaching
coaching → LLM
LLM → schema validator
Pipeline Tests

Validate the full coaching flow.

Android request
 ↓
API
 ↓
engine
 ↓
coaching logic
 ↓
LLM explanation
 ↓
response
Engine Tests

Validate:

evaluation correctness

move ordering

latency limits

JNI Bridge Tests

Critical tests include:

board state synchronization

move encoding correctness

engine command parsing

Analytics Tests

Ensure analytics produce consistent results.

Example:

repeated games produce consistent profile updates

mistake frequencies calculated correctly

LLM Schema Tests

Verify that:

responses match schema

fields exist

enums are valid

Regression Tests

Regression tests prevent reintroducing past bugs.

Every bug fix should add or update a regression test.

Performance Tests

Validate:

engine latency

API responsiveness

concurrent request handling

cache effectiveness

Pre-Push Checklist

Before pushing:

run all tests

confirm test integrity

verify no architectural rule is violated

ensure commits describe the development session

Forbidden Testing Practices

The following are prohibited:

disabling tests to push code

modifying expected values to hide bugs

removing failing tests

bypassing schema validation

CI/CD Recommendation

CI pipeline should run:

unit tests
integration tests
schema validation
lint checks

A push must fail automatically if tests fail.
