import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { DEFAULT_MODEL } from '@/utils/vendorConfig';

export type AIVendor = 'openai' | 'google' | 'anthropic' | 'vllm' | 'ollama';

const STORAGE_KEY = 'queryweaver_ai_settings';

interface StoredSettings {
  vendor: AIVendor;
  modelName: string;
  temperature: number;
  customEndpoint: string;
  systemPrompt: string;
}

function loadStoredSettings(): StoredSettings {
  const defaults: StoredSettings = {
    vendor: 'openai',
    modelName: DEFAULT_MODEL,
    temperature: 0.2,
    customEndpoint: '',
    systemPrompt: 'You are an expert SQL analyst. Convert the user question to a correct SQL query based on the database schema.',
  };
  
  if (typeof window === 'undefined') {
    return defaults;
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        vendor: parsed.vendor || defaults.vendor,
        modelName: parsed.modelName || defaults.modelName,
        temperature: typeof parsed.temperature === 'number' ? parsed.temperature : defaults.temperature,
        customEndpoint: parsed.customEndpoint || defaults.customEndpoint,
        systemPrompt: parsed.systemPrompt || defaults.systemPrompt,
      };
    }
  } catch { /* ignore corrupt storage */ }
  return defaults;
}

interface SettingsContextType {
  vendor: AIVendor;
  apiKey: string | null;
  modelName: string;
  isApiKeyValid: boolean;
  temperature: number;
  customEndpoint: string;
  systemPrompt: string;
  setVendor: (vendor: AIVendor) => void;
  setApiKey: (key: string | null) => void;
  setModelName: (model: string) => void;
  setIsApiKeyValid: (valid: boolean) => void;
  setTemperature: (temp: number) => void;
  setCustomEndpoint: (url: string) => void;
  setSystemPrompt: (prompt: string) => void;
  clearSettings: () => void;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
};

interface SettingsProviderProps {
  children: ReactNode;
}

export const SettingsProvider: React.FC<SettingsProviderProps> = ({ children }) => {
  const stored = loadStoredSettings();
  const [vendor, setVendor] = useState<AIVendor>(stored.vendor);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [modelName, setModelName] = useState<string>(stored.modelName);
  const [isApiKeyValid, setIsApiKeyValid] = useState<boolean>(false);
  
  // Extended fields
  const [temperature, setTemperature] = useState<number>(stored.temperature);
  const [customEndpoint, setCustomEndpoint] = useState<string>(stored.customEndpoint);
  const [systemPrompt, setSystemPrompt] = useState<string>(stored.systemPrompt);

  // Persist settings to localStorage (never persist the API key)
  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY, 
      JSON.stringify({ vendor, modelName, temperature, customEndpoint, systemPrompt })
    );
  }, [vendor, modelName, temperature, customEndpoint, systemPrompt]);

  const clearSettings = () => {
    setVendor('openai');
    setApiKey(null);
    setModelName(DEFAULT_MODEL);
    setIsApiKeyValid(false);
    setTemperature(0.2);
    setCustomEndpoint('');
    setSystemPrompt('You are an expert SQL analyst. Convert the user question to a correct SQL query based on the database schema.');
    localStorage.removeItem(STORAGE_KEY);
  };

  return (
    <SettingsContext.Provider
      value={{
        vendor,
        apiKey,
        modelName,
        isApiKeyValid,
        temperature,
        customEndpoint,
        systemPrompt,
        setVendor,
        setApiKey,
        setModelName,
        setIsApiKeyValid,
        setTemperature,
        setCustomEndpoint,
        setSystemPrompt,
        clearSettings,
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
};
