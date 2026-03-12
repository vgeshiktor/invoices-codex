export interface SafeJsonStringifyOptions {
  includeErrorStack?: boolean;
  indent?: number;
}

export const safeJsonStringify = (
  value: unknown,
  options: SafeJsonStringifyOptions = {},
): string => {
  const includeErrorStack = options.includeErrorStack ?? false;
  const indent = options.indent ?? 2;

  try {
    const seen = new WeakSet<object>();
    const json = JSON.stringify(
      value,
      (key, currentValue: unknown) => {
        if (key === 'stack' && !includeErrorStack) {
          return undefined;
        }

        if (currentValue instanceof Error) {
          return {
            message: currentValue.message,
            name: currentValue.name,
            ...(includeErrorStack ? { stack: currentValue.stack } : {}),
          };
        }

        if (typeof currentValue === 'bigint') {
          return currentValue.toString();
        }

        if (currentValue && typeof currentValue === 'object') {
          if (seen.has(currentValue)) {
            return '[Circular]';
          }
          seen.add(currentValue);
        }

        return currentValue;
      },
      indent,
    );

    return json ?? String(value);
  } catch {
    return String(value);
  }
};
