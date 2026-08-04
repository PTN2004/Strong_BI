import type { AIVendor } from '@/contexts/SettingsContext';

export interface VendorConfig {
  value: AIVendor;
  label: string;
  keyPrefix: string;
  exampleModel: string;
}

export const AI_VENDORS: VendorConfig[] = [
  { value: 'openai', label: 'OpenAI', keyPrefix: 'sk-', exampleModel: 'gpt-4.1' },
  { value: 'google', label: 'Google', keyPrefix: '', exampleModel: 'gemini-3-pro-preview' },
  { value: 'anthropic', label: 'Anthropic', keyPrefix: 'sk-ant-', exampleModel: 'claude-sonnet-4-5-20250929' },
  { value: 'vllm', label: 'vLLM (Custom OpenAI Server)', keyPrefix: '', exampleModel: 'Qwen/Qwen2.5-Coder-7B-Instruct' },
  { value: 'ollama', label: 'Ollama (Local Host)', keyPrefix: '', exampleModel: 'llama3' },
];

export const DEFAULT_MODEL = 'gpt-4.1';

const VENDOR_PREFIX_MAP: Record<AIVendor, string> = {
  openai: 'openai',
  google: 'gemini',
  anthropic: 'anthropic',
  vllm: 'vllm',
  ollama: 'ollama',
};

export function getVendorPrefix(vendor: AIVendor): string {
  return VENDOR_PREFIX_MAP[vendor] ?? vendor;
}

export function getVendorConfig(vendor: AIVendor): VendorConfig | undefined {
  return AI_VENDORS.find(v => v.value === vendor);
}

export function validateApiKeyFormat(key: string, vendor: AIVendor): string | null {
  if (!key.trim()) {
    return 'Please enter an API key';
  }

  const config = getVendorConfig(vendor);
  if (config?.keyPrefix && !key.startsWith(config.keyPrefix)) {
    return `Invalid API key format. ${config.label} keys should start with "${config.keyPrefix}"`;
  }

  return null;
}
