export function getRequiredEnv(
  key: string,
  source: Record<string, string | undefined>,
): string {
  const value = source[key]
  if (value === undefined) {
    throw new Error(`Missing required env var: ${key}`)
  }

  return value
}
