import { describe, expect, it } from 'vitest'

import { getRequiredEnv } from './env'

describe('getRequiredEnv', () => {
  it('returns value for an existing env var', () => {
    expect(getRequiredEnv('API_BASE_URL', { API_BASE_URL: 'http://localhost:8000' })).toBe(
      'http://localhost:8000',
    )
  })

  it('allows an empty string when key is present', () => {
    expect(getRequiredEnv('API_BASE_URL', { API_BASE_URL: '' })).toBe('')
  })

  it('throws when env var is missing', () => {
    expect(() => getRequiredEnv('API_BASE_URL', {})).toThrow(
      'Missing required env var: API_BASE_URL',
    )
  })
})
