import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Sanitize the config to remove any Python-style format strings hallucinated by the LLM
// e.g. {value:,.0f} -> {value}
export const sanitizeEChartsFormatter = (obj: any): any => {
  if (typeof obj === 'string') {
    return obj.replace(/\{value:[^}]+\}/g, '{value}');
  }
  if (Array.isArray(obj)) {
    return obj.map(sanitizeEChartsFormatter);
  }
  if (obj !== null && typeof obj === 'object') {
    const newObj: any = {};
    for (const key in obj) {
      newObj[key] = sanitizeEChartsFormatter(obj[key]);
    }
    return newObj;
  }
  return obj;
};
