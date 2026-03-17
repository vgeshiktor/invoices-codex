import { describe, expect, it } from 'vitest';
import { AUTH_ACCESS_TOKEN_STORAGE_KEY } from '../../app/authSession.constants';
import { getRuntimeAuthHeaders } from './runtimeAuth';

describe('getRuntimeAuthHeaders', () => {
  it('prefers bearer auth from the stored session token', () => {
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, 'session-token');

    expect(getRuntimeAuthHeaders()).toEqual({
      Authorization: 'Bearer session-token',
    });
  });
});
