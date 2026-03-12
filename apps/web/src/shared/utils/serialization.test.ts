import { describe, expect, it } from 'vitest';
import { safeJsonStringify } from './serialization';

describe('safeJsonStringify', () => {
  it('serializes regular and bigint values', () => {
    const result = safeJsonStringify({
      count: 42n,
      status: 'ok',
    });

    expect(result).toContain('"count": "42"');
    expect(result).toContain('"status": "ok"');
  });

  it('does not throw on circular objects', () => {
    const value: { id: string; self?: unknown } = { id: 'node-1' };
    value.self = value;

    expect(() => safeJsonStringify(value)).not.toThrow();
    expect(safeJsonStringify(value)).toContain('"self": "[Circular]"');
  });
});
