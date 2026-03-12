import { describe, expect, it } from 'vitest';
import { safeJsonStringify } from './serialization';

describe('safeJsonStringify', () => {
  it('redacts error stack by default and handles bigint + circular values', () => {
    const error = new Error('boom');
    const payload: {
      count: bigint;
      error: Error;
      self?: unknown;
    } = {
      count: 123n,
      error,
    };
    payload.self = payload;

    const json = safeJsonStringify(payload);

    expect(json).toContain('"name": "Error"');
    expect(json).toContain('"message": "boom"');
    expect(json).toContain('"count": "123"');
    expect(json).toContain('"self": "[Circular]"');
    expect(json).not.toContain('"stack"');
  });

  it('includes error stack when explicitly requested', () => {
    const json = safeJsonStringify(new Error('with-stack'), {
      includeErrorStack: true,
    });
    expect(json).toContain('"stack"');
  });
});
